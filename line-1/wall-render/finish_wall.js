'use strict';
// Local image finishing only. No network, packages, environment or shell calls.
const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');
const crypto = require('node:crypto');
const encodeJPEG = require('./vendor/jpeg_encoder.js');

function workspaceFile(name) {
  const root = fs.realpathSync('.');
  const resolved = fs.existsSync(name) ? fs.realpathSync(name) : path.join(fs.realpathSync(path.dirname(name)), path.basename(name));
  if (!resolved.startsWith(root + path.sep)) throw Error('file must be inside workspace');
  return resolved;
}

function crc32(bytes) {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function decodePNG(filename) {
  const raw = fs.readFileSync(workspaceFile(filename));
  if (!raw.subarray(0, 8).equals(Buffer.from([137,80,78,71,13,10,26,10]))) throw Error('not PNG');
  let width, height, channels;
  const parts = [];
  for (let at = 8; at < raw.length;) {
    const size = raw.readUInt32BE(at);
    const kind = raw.toString('ascii', at + 4, at + 8);
    const data = raw.subarray(at + 8, at + 8 + size);
    if (at + size + 12 > raw.length || crc32(raw.subarray(at + 4, at + 8 + size)) !== raw.readUInt32BE(at + 8 + size)) throw Error('invalid PNG chunk');
    if (kind === 'IHDR') {
      width = data.readUInt32BE(0); height = data.readUInt32BE(4);
      if (data[8] !== 8 || ![2,6].includes(data[9]) || data[10] || data[11] || data[12]) throw Error('requires noninterlaced RGB8/RGBA8');
      channels = data[9] === 2 ? 3 : 4;
      if (width > 4096 || height > 4096) throw Error('image exceeds finishing budget');
    }
    if (kind === 'IDAT') parts.push(data);
    at += size + 12;
    if (kind === 'IEND') break;
  }
  const stride = width * channels;
  const filtered = zlib.inflateSync(Buffer.concat(parts), {maxOutputLength: (stride + 1) * height});
  if (filtered.length !== (stride + 1) * height) throw Error('invalid pixel length');
  const pixels = Buffer.alloc(stride * height);
  for (let y = 0; y < height; y++) {
    const filter = filtered[y * (stride + 1)];
    if (filter > 4) throw Error('invalid PNG filter');
    for (let x = 0; x < stride; x++) {
      const a = x >= channels ? pixels[y * stride + x - channels] : 0;
      const b = y ? pixels[(y - 1) * stride + x] : 0;
      const c = y && x >= channels ? pixels[(y - 1) * stride + x - channels] : 0;
      const p = a + b - c;
      const pa = Math.abs(p-a), pb = Math.abs(p-b), pc = Math.abs(p-c);
      const paeth = pa <= pb && pa <= pc ? a : pb <= pc ? b : c;
      const prediction = [0, a, b, Math.floor((a+b)/2), paeth][filter];
      pixels[y * stride + x] = (filtered[y * (stride + 1) + 1 + x] + prediction) & 255;
    }
  }
  return {width, height, channels, pixels};
}

function chunk(kind, data) {
  const body = Buffer.concat([Buffer.from(kind), data]);
  const length = Buffer.alloc(4), crc = Buffer.alloc(4);
  length.writeUInt32BE(data.length); crc.writeUInt32BE(crc32(body));
  return Buffer.concat([length, body, crc]);
}

function encodePNG(image) {
  const {width, height, channels, pixels} = image;
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width); header.writeUInt32BE(height, 4);
  header[8] = 8; header[9] = channels === 3 ? 2 : 6;
  const stride = width * channels;
  const scan = Buffer.alloc((stride + 1) * height);
  for (let y = 0; y < height; y++) {
    scan[y * (stride + 1)] = 1;
    for (let x = 0; x < stride; x++) scan[y * (stride + 1) + 1 + x] = (pixels[y*stride+x] - (x >= channels ? pixels[y*stride+x-channels] : 0)) & 255;
  }
  return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]), chunk('IHDR',header), chunk('IDAT',zlib.deflateSync(scan,{level:9})), chunk('IEND',Buffer.alloc(0))]);
}

function composite(ancestor, generated) {
  if (ancestor.width !== 1254 || ancestor.height !== 1254 || generated.width !== 1254 || generated.height !== 1254 || ancestor.channels !== generated.channels) throw Error('expected matching 1254-square images');
  // Only this formerly empty patch is eligible. Existing painted figures begin outside it.
  const bounds = [305, 322, 649, 535];
  const [left, top, right, bottom] = bounds;
  const result = {...ancestor, pixels: Buffer.from(ancestor.pixels)};
  for (let y = top; y < bottom; y++) for (let x = left; x < right; x++) {
    const blend = Math.min(1, (x-left)/12, (right-1-x)/12, (y-top)/12, (bottom-1-y)/12);
    for (let channel = 0; channel < result.channels; channel++) {
      const at = (y*result.width+x)*result.channels+channel;
      result.pixels[at] = Math.round(ancestor.pixels[at]*(1-blend) + generated.pixels[at]*blend);
    }
  }
  let unchangedOutside = true, changedPixels = 0;
  for (let y=0; y<result.height; y++) for(let x=0; x<result.width; x++) {
    const at=(y*result.width+x)*result.channels;
    const changed = !result.pixels.subarray(at,at+result.channels).equals(ancestor.pixels.subarray(at,at+result.channels));
    if (changed) changedPixels++;
    if (changed && !(left<=x && x<right && top<=y && y<bottom)) unchangedOutside=false;
  }
  return {result, bounds, unchangedOutside, changedPixels};
}

function preview(image) {
  const size=512, rgba=Buffer.alloc(size*size*4);
  // Area resampling preserves the whole square framing and averages fine rock texture.
  for(let y=0;y<size;y++) for(let x=0;x<size;x++) {
    const x0=x*image.width/size, x1=(x+1)*image.width/size;
    const y0=y*image.height/size, y1=(y+1)*image.height/size;
    const sums=[0,0,0]; let weight=0;
    for(let yy=Math.floor(y0); yy<Math.ceil(y1); yy++) for(let xx=Math.floor(x0); xx<Math.ceil(x1); xx++) {
      const w=(Math.min(x1,xx+1)-Math.max(x0,xx))*(Math.min(y1,yy+1)-Math.max(y0,yy));
      for(let c=0;c<3;c++) sums[c]+=image.pixels[(yy*image.width+xx)*image.channels+c]*w;
      weight+=w;
    }
    for(let c=0;c<3;c++) rgba[(y*size+x)*4+c]=Math.round(sums[c]/weight);
    rgba[(y*size+x)*4+3]=255;
  }
  return encodeJPEG({data:rgba,width:size,height:size},75).data;
}

if (require.main === module) {
  const [command, first, second, third] = process.argv.slice(2);
  if (command === 'composite' && first && second && third) {
    const output=workspaceFile(third);
    const merged=composite(decodePNG(first),decodePNG(second));
    fs.writeFileSync(output,encodePNG(merged.result));
    console.log(JSON.stringify({bounds:merged.bounds, unchanged_outside:merged.unchangedOutside, changed_pixels:merged.changedPixels, sha256:crypto.createHash('sha256').update(fs.readFileSync(output)).digest('hex')}));
  } else if (command === 'preview' && first && second && !third) {
    const jpeg=preview(decodePNG(first));
    if (jpeg.length>100000) throw Error('preview exceeds 100 KB');
    fs.writeFileSync(workspaceFile(second),jpeg);
    console.log(JSON.stringify({format:'JPEG',width:512,height:512,bytes:jpeg.length}));
  } else throw Error('usage: composite ancestor.png generated.png output.png | preview wall.png preview.jpg');
}

module.exports = {decodePNG, encodePNG, composite, preview};

// Natural Noise sketch nn4 — tuned for img2 (dried grass).
// img2 is high-contrast B&W with lots of fine texture — needs more aggressive
// disruption to lose the original form while keeping the energy pattern.

let img;
let gArt;

// --- TWEAK THESE ---

const numbBands = 8;

const colours = [
  "#684343ff",
  "#35231aff",
  "#9c8458ff",
  "#036c44",
  "#222745",
  "#014fcd",
  "#733e3d",
  "#f3651b"
];

// Transfer function: 'invert-s' | 'wave' | 'threshold-scatter'
const transferFn = 'wave';

// --- END TWEAKS ---

function preload() {
  img = loadImage("img2.png");
}

function setup() {
  createCanvas(800, 800);

  let imgGrey = createImage(img.width, img.height);
  img.loadPixels();
  imgGrey.loadPixels();

  for (let x = 0; x < img.width; x++) {
    for (let y = 0; y < img.height; y++) {
      let pixel = img.get(x, y);
      let gray = 0.299 * pixel[0] + 0.587 * pixel[1] + 0.114 * pixel[2];
      let v = applyTransfer(gray / 255, x, y);
      imgGrey.set(x, y, [v * 255, v * 255, v * 255, 255]);
    }
  }
  imgGrey.updatePixels();

  gArt = createGraphics(img.width, img.height);

  for (let i = 0; i < imgGrey.width; i++) {
    for (let j = 0; j < imgGrey.height; j++) {
      let pixel = imgGrey.get(i, j);
      const band = int((pixel[0] / 255) * numbBands);
      const colour = band % colours.length;
      gArt.stroke(colours[colour]);
      gArt.point(i, j);
    }
  }
}

function applyTransfer(x, px, py) {
  switch (transferFn) {
    case 'wave':
      // Sine wave remapping — wraps the tonal range fewer times.
      // 2 cycles instead of 6: enough to break the grass texture
      // but keeps broader tonal regions intact. More painterly, less noisy.
      return (Math.sin(x * Math.PI * 2) + 1) / 2;

    case 'invert-s':
      // Invert then gentle S-curve — swaps light/dark first so the
      // grass strands (bright) become the dark bands. Breaks the
      // recognisable "bright lines on dark" pattern of the original.
      let inv = 1 - x;
      return 1 / (1 + Math.exp(-5 * (inv - 0.5)));

    case 'threshold-scatter':
      // Position-dependent threshold — the cutoff shifts based on
      // pixel position, creating diagonal banding that overrides
      // the original texture. Fine detail gets absorbed into the
      // position-driven pattern.
      let threshold = ((px + py) % 80) / 80;
      return x > threshold ? 1 : 0;

    default:
      return x;
  }
}

function draw() {
  image(gArt, 0, 0, width, height);
}

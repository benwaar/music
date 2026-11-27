// Natural Noise sketch — improved banding with controllable transfer functions.
// Replaces the steep sigmoid with multiple options for richer visual output.
//
// CONTROLS:
//   - Change transferFn to try different mappings
//   - Adjust numbBands for more/fewer colour bands
//   - Change the colours array for different palettes

let img;
let gArt;

// --- TWEAK THESE ---

const numbBands = 12;

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

// Transfer function: 'linear' | 'gentle-s' | 'contrast' | 'posterize' | 'sigmoid'
const transferFn = 'gentle-s';

// --- END TWEAKS ---

function preload() {
  img = loadImage("img1.png");
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
      let v = applyTransfer(gray / 255);
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

function applyTransfer(x) {
  switch (transferFn) {
    case 'linear':
      // Full range, no distortion. Every grey level maps proportionally.
      return x;

    case 'gentle-s':
      // Mild S-curve — boosts contrast without crushing mid-tones.
      // Steepness 4 instead of 10. Keeps ~80% of the tonal range usable.
      return 1 / (1 + Math.exp(-4 * (x - 0.5)));

    case 'contrast':
      // Power curve — darkens shadows, preserves highlights.
      // Good for images with lots of bright detail (like foliage).
      return Math.pow(x, 0.6);

    case 'posterize':
      // Hard quantise into steps — sharp band edges, retro feel.
      let steps = numbBands;
      return Math.floor(x * steps) / steps;

    case 'sigmoid':
      // Original steep sigmoid — mostly binary output.
      return 1 / (1 + Math.exp(-10 * (x - 0.5)));

    default:
      return x;
  }
}

function draw() {
  image(gArt, 0, 0, width, height);
}

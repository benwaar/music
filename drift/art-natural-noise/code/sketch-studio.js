// Natural Noise — interactive studio with sliders.
// Tweak parameters in real-time, see the output update live.
// Designed to work alongside drift for the creative iteration workflow.

let img;
let gArt;
let needsRedraw = true;

// Sliders
let sliderBands, sliderSteepness, sliderCycles, sliderGamma;
let selectTransfer, selectImage;
let btnSave;

// Images
let img1, img2;

function preload() {
  img1 = loadImage("img1.png");
  img2 = loadImage("img2.png");
}

function setup() {
  let canvas = createCanvas(800, 800);
  canvas.position(220, 10);

  gArt = createGraphics(800, 800);

  // --- Controls panel ---
  let x = 10;
  let y = 10;
  let w = 190;

  createElement('h3', 'Natural Noise').position(x, y);
  y += 40;

  // Image selector
  createElement('label', 'Image').position(x, y);
  y += 20;
  selectImage = createSelect();
  selectImage.position(x, y);
  selectImage.size(w);
  selectImage.option('img1 — foliage');
  selectImage.option('img2 — dried grass');
  selectImage.changed(() => { needsRedraw = true; });
  y += 35;

  // Transfer function
  createElement('label', 'Transfer function').position(x, y);
  y += 20;
  selectTransfer = createSelect();
  selectTransfer.position(x, y);
  selectTransfer.size(w);
  selectTransfer.option('gentle-s');
  selectTransfer.option('linear');
  selectTransfer.option('wave');
  selectTransfer.option('posterize');
  selectTransfer.option('contrast');
  selectTransfer.option('invert-s');
  selectTransfer.option('sigmoid');
  selectTransfer.changed(() => { needsRedraw = true; });
  y += 35;

  // Bands
  createElement('label', 'Bands').position(x, y);
  y += 20;
  sliderBands = createSlider(2, 24, 10, 1);
  sliderBands.position(x, y);
  sliderBands.size(w);
  sliderBands.input(() => { needsRedraw = true; });
  y += 35;

  // Steepness (for sigmoid / gentle-s / invert-s)
  createElement('label', 'Steepness').position(x, y);
  y += 20;
  sliderSteepness = createSlider(1, 20, 4, 0.5);
  sliderSteepness.position(x, y);
  sliderSteepness.size(w);
  sliderSteepness.input(() => { needsRedraw = true; });
  y += 35;

  // Wave cycles (for wave mode)
  createElement('label', 'Wave cycles').position(x, y);
  y += 20;
  sliderCycles = createSlider(0.5, 8, 2, 0.5);
  sliderCycles.position(x, y);
  sliderCycles.size(w);
  sliderCycles.input(() => { needsRedraw = true; });
  y += 35;

  // Gamma (for contrast mode)
  createElement('label', 'Gamma').position(x, y);
  y += 20;
  sliderGamma = createSlider(0.1, 3.0, 0.6, 0.1);
  sliderGamma.position(x, y);
  sliderGamma.size(w);
  sliderGamma.input(() => { needsRedraw = true; });
  y += 45;

  // Save button
  btnSave = createButton('Save PNG');
  btnSave.position(x, y);
  btnSave.size(w, 30);
  btnSave.mousePressed(() => {
    saveCanvas('natural-noise-output', 'png');
  });
  y += 45;

  // Colours (fixed for now — could add picker later)
  createElement('p', 'Colours: earthy palette (8)').position(x, y).style('font-size', '11px').style('color', '#666');
}

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

function renderArt() {
  let src = selectImage.value().startsWith('img1') ? img1 : img2;
  let numbBands = sliderBands.value();
  let steepness = sliderSteepness.value();
  let cycles = sliderCycles.value();
  let gamma = sliderGamma.value();
  let tfn = selectTransfer.value();

  let imgGrey = createImage(src.width, src.height);
  src.loadPixels();
  imgGrey.loadPixels();

  for (let x = 0; x < src.width; x++) {
    for (let y = 0; y < src.height; y++) {
      let pixel = src.get(x, y);
      let gray = 0.299 * pixel[0] + 0.587 * pixel[1] + 0.114 * pixel[2];
      let v = applyTransfer(gray / 255, tfn, steepness, cycles, gamma, numbBands);
      imgGrey.set(x, y, [v * 255, v * 255, v * 255, 255]);
    }
  }
  imgGrey.updatePixels();

  gArt.clear();
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

function applyTransfer(x, tfn, steepness, cycles, gamma, bands) {
  switch (tfn) {
    case 'linear':
      return x;

    case 'gentle-s':
      return 1 / (1 + Math.exp(-steepness * (x - 0.5)));

    case 'sigmoid':
      return 1 / (1 + Math.exp(-steepness * (x - 0.5)));

    case 'wave':
      return (Math.sin(x * Math.PI * cycles) + 1) / 2;

    case 'posterize':
      return Math.floor(x * bands) / bands;

    case 'contrast':
      return Math.pow(x, gamma);

    case 'invert-s':
      let inv = 1 - x;
      return 1 / (1 + Math.exp(-steepness * (inv - 0.5)));

    default:
      return x;
  }
}

function draw() {
  if (needsRedraw) {
    needsRedraw = false;
    renderArt();
  }
  image(gArt, 0, 0, width, height);
}

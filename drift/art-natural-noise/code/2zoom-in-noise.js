let bg;

const noiseScale = 0.01;

function setup() {
  createCanvas(600, 600);
  bg = createGraphics(width, height);
  createBG();
}

function draw() {
  image(bg, 0, 0, width, height);
}

function createBG() {
  // Iterate from left to right.
  for (let i = 0; i < bg.width; i++) {
    // Iterate from top to bottom.
    for (let j = 0; j < bg.height; j++ ) {
      // Noise is a value between 0 and 1
      const n = noise(i * noiseScale, j * noiseScale);
      // Convert the noise value to a colour between black and white
      bg.stroke(n * 255); 
      bg.point(i, j);
    }
  }
}

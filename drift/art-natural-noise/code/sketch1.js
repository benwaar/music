// https://p5js.org/reference/p5/noise/
// https://www.youtube.com/watch?v=zJnSwHnYLhs&list=PLlaA0JvEhcG-VN40Zt1jJTW6mvm6oHtlx

const noiseLevel = 255;
const noiseScale = 0.016;

const colours = [
  "#6e623d",
  "#decf6d",
  "#2424ab",
  "#a6a6ed",
];

const numBands = 16;

function setup() {
  createCanvas(800, 800);
  background(200);
  
  // Iterate from top to bottom.
  for (let y = 0; y < height; y += 1) {
    // Iterate from left to right.
    for (let x = 0; x < width; x += 1) {
      // Scale the input coordinates.
      let nx = noiseScale * x;
      let ny = noiseScale * y;

      // Compute the noise value.
      let n =  noise(nx, ny);
      // Turn the noise into a colour
      const band = int(n * numBands);
      const colour = band % colours.length;

      // Draw the point.
      stroke(colours[colour]);
      point(x, y);
    }
  }
  
  describe('Noise Art 1 - Ken Perlin - Tron = Noise Art.');
}
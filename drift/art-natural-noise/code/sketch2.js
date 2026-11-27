// https://p5js.org/reference/p5/noise/
// https://www.youtube.com/watch?v=zJnSwHnYLhs&list=PLlaA0JvEhcG-VN40Zt1jJTW6mvm6oHtlx

/*
const noiseLevel = 118;
const noiseScale = 0.0048;

const colours = [
  "#733e3d",
  "#f3651b",
  "#7e6a45"
];
*/

/*
const noiseLevel = 123;
const noiseScale = 0.0033;

const colours = [
  "#222745",
  "#014fcd",
  "#7e6a45",
  "#036c44"
];

*/

const noiseLevel = 321;
const noiseScale = 0.00789;

const colours = [
  "#036c44",
  "#222745",
  "#7e6a45"
];


/*
red 733e3d
orange f3651b
gold 7e6a45

blue 222745
blue2 014fcd

green 036c44
*/

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
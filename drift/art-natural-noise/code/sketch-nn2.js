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

/*

const noiseLevel = 321;
const noiseScale = 0.00789;

const colours = [
  "#036c44",
  "#222745",
  "#7e6a45"
];

*/

/*
red 733e3d
orange f3651b
gold 7e6a45

blue 222745
blue2 014fcd

green 036c44
*/

/*
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

*/



let img;
let imgGreyScale;
let gArt;


const numbBands = 2;

const colours = [
  "#684343ff",
  "#35231aff",
  "#9c8458ff",
  "#036c44",
  "#222745"
];

function preload(){
  //img = loadImage("nn2.png");
  imgGreyScale = loadImage("img2.png");
}

function setup() {
  createCanvas(800, 800);

  //imgGreyScale = createImage(img.width, img.height);

  // Load the pixels of all images.
  //img.loadPixels();
  imgGreyScale.loadPixels();


  /*
  
  // Apply the function f to each pixel of the original image and store the result in the transformed image.
  for (let x = 0; x < img.width; x++) {
    for (let y = 0; y < img.height; y++) {
      // Get the color of the pixel.
      let pixel = img.get(x, y);
      // Convert the color to grayscale.
      let gray = 0.299*pixel[0] + 0.587*pixel[1] + 0.114*pixel[2];
      // Normalize the gray value to be between 0 and 1, and apply the function f.
      let value0 = f(gray / 255);
      // Map the value back to the range 0-255 and set the pixel in the transformed image.
      imgGreyScale.set(x, y, [value0 * 255, value0 * 255, value0 * 255, 255]);
    }
  }


  
  // Update the pixel array of the transformed image.
  imgGreyScale.updatePixels();

  */

  gArt = createGraphics(imgGreyScale.width, imgGreyScale.height);

  // Iterate from left to right.
  for (let i = 0; i < imgGreyScale.width; i++) {
    // Iterate from top to bottom.
    for (let j = 0; j < imgGreyScale.height; j++ ) {
      let pixel = imgGreyScale.get(i, j);
      //gArt.stroke(pixel); 

      if ((i == 10) && (j == 10)) {
        console.log(pixel[0]);
      }
      
      const band = int(pixel[0] * numbBands);
      const colour = band % colours.length;
      gArt.stroke(colours[colour]); 
      
      gArt.point(i, j);
    }
  }

}

function f(x) {
  // replace this with your actual function
  return 1 / (1 + Math.exp(-10 * (x - 0.5)));
}


function draw() {
  //image(img, 0, 0, width, height);
  //image(imgGreyScale, 0, 0, width, height);
  image(gArt, 0, 0, width, height);
}





























import ExtentInteraction from 'ol/interaction/Extent.js';
import Map from 'ol/Map.js';
import OSM from 'ol/source/OSM.js';
import TileLayer from 'ol/layer/Tile.js';
import View from 'ol/View.js';
import {shiftKeyOnly} from 'ol/events/condition.js';
import {transform} from "ol/proj";

let left = 0;
let right = 0;
let top = 0;
let bottom = 0;

// Used for OpenStreetMap
const map = new Map({
  layers: [
    new TileLayer({
      source: new OSM(),
    }),
  ],
  target: 'map',
  view: new View({
    center: transform([172.5, -43], 'EPSG:4326', 'EPSG:3857'),
    zoom: 4.5,
  }),
});

const extent = new ExtentInteraction({condition: shiftKeyOnly});
map.addInteraction(extent);

// Used for display current coordinates
extent.on('extentchanged', (event) => {
  const extentCoordinates = event.extent;
  const infoElement1 = document.getElementById('figure1');
  const infoElement2 = document.getElementById('figure2');
  const infoElement3 = document.getElementById("info");

  // Lower left corner coordinate
  const minLonLat = transformToLatLon([extentCoordinates[0], extentCoordinates[1]]);

  // Upper right corner coordinate
  const maxLonLat = transformToLatLon([extentCoordinates[2], extentCoordinates[3]]);

  // If longitude is bigger than 180 degrees
  const normalized_lower_left_longitude = (minLonLat[0] + 180) % 360 - 180
  const normalized_upper_right_longitude = (maxLonLat[0] + 180) % 360 - 180
  // Lower left corner coordinate
  infoElement1.innerText = normalized_lower_left_longitude + "," + minLonLat[1];
  // Upper right corner coordinate
  infoElement2.innerText = normalized_upper_right_longitude + "," + maxLonLat[1];
  infoElement3.innerText = "Updated";

  left = normalized_lower_left_longitude;
  top = maxLonLat[1];
  right = normalized_upper_right_longitude;
  bottom = minLonLat[1];
})

//
// function executeCommand() {
//   fetch('/execute-command')
//     .then(response => response.text())
//     .then(data => {
//       document.getElementById('output').innerHTML = data;
//     })
//     .catch(error => console.error('Error:', error));
// }
//
// // Send data to server middleware
// const sendDataToMiddleware = async () => {
//   const dataToSend = {key: 'value'};
//
//   try {
//     const response = await fetch('api/receiveData', {
//       method: 'POST',
//       headers: {
//         'Content-Type': 'application/json',
//       },
//       body: JSON.stringify(dataToSend),
//     });
//
//     if (response.ok) {
//       console.log('Data sent to middleware successfully.');
//     } else {
//       console.error('Failed to send data to middleware', response.statusText);
//     }
//   } catch (error) {
//     console.error("An error occurred:", error);
//   }
// };


function transformToLatLon(coord) {
  return transform(coord, 'EPSG:3857', 'EPSG:4326');
}


// Send parameters to server
document.getElementById('sendInfo').addEventListener('click', () => {
  const searchForm = document.getElementById('searchForm');
  if (left === 0 & right === 0 & top === 0 & bottom === 0){
    window.alert("Please select the region first!");
  }else {
    const postData = {
    // Bounding box Coordinates
    left: left,
    bottom: bottom,
    right: right,
    top: top,
    // Number of posts
    numOfPosts: searchForm.elements['z'].value,
    // Social Media sources
    YouTube: document.getElementById('youtubeCheckbox').classList.contains('selected'),
    Reddit: document.getElementById('redditCheckbox').classList.contains('selected'),
    Twitter: document.getElementById('twitterCheckbox').classList.contains('selected'),
    // Date range
    timeRangeStart: searchForm.elements['t_start'].value,
    timeRangeEnd: searchForm.elements['t_end'].value
  };

  fetch('http://130.123.76.70:3001/api/postData', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(postData)
  })
  .then(response => response.json())
  .then(data => {
    console.log('Response from server:', data);
    document.getElementById('output').innerText = data.message;
  })
  .catch(error => {
    console.error('Error:', error);
  });
  }

})


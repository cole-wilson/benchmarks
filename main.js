var app = new Vue({
	el: 'main',
	data: {
		current_pid: null,
		current_benchmark: {},
		zoom_in: false,
		shown_benchmarks: [],
		markers: {}, // https://stackoverflow.com/questions/13004226/how-to-interact-with-leaflet-marker-layer-from-outside-the-map

	},
	methods: {
		chooseMarker: function(pid){
			if (this.markers[pid])
				this.markers[pid].openPopup(this.markers[pid].getLatLng())
		},
		highlightMarker: function(pid){this.markers[pid].bringToFront().setStyle({color:"blue"})},
		unhighlightMarker: function(pid){this.markers[pid].bringToFront().setStyle({color:"red"})},
		toDMS:function(D, lng) { // https://stackoverflow.com/questions/5786025/decimal-degrees-to-degrees-minutes-and-seconds-in-javascript#5786281
			let dir= D < 0 ? (lng ? "W" : "S") : lng ? "E" : "N";
			let deg= 0 | (D < 0 ? (D = -D) : D);
			let min= 0 | (((D += 1e-9) % 1) * 60);
			let sec= (0 | (((D * 60) % 1) * 6000)) / 100;
			return `${dir} ${deg}°${min}'${sec}"`;
		},
		openImage:function(url) {
			window.open(url, "_blank", "popup,height=400,width=500")
		}
	}
});

let markerStyle = {color: "red",radius: 3,opacity: 0,fillOpacity: 1,weight: 0}
var marker_layer;

async function getBenchmarkData(pid) {
	let response = await fetch("https://bmserver.cole.ws/"+pid+".json")
	// let response = await fetch("http://localhost:8081/"+pid+".json")
	app.current_benchmark = await response.json();
}

function popupClicked(layer) {
	let pid = layer.feature.properties.pid;
	location.hash = pid;
	app.current_pid = pid;
	getBenchmarkData(pid);
	return pid;
}

function refreshMap(geojson) {
	app.markers = {};
	if (marker_layer) marker_layer.remove();
	marker_layer = L.geoJSON(geojson, {
		pointToLayer: function(feature, latlng){
			if (map.getZoom()>15) markerStyle.radius = 10;
			else if (map.getZoom()>9) markerStyle.radius = 3;
			else markerStyle.radius = 1;
			let marker = L.circleMarker(latlng, markerStyle);
			app.markers[feature.properties.pid] = marker;
			return marker;
		},
		onEachFeature: function(_, layer){layer.bindPopup(popupClicked)},
		attribution: `<a href="https://www.ngs.noaa.gov/datasheets/">NGS</a>`
	});
	marker_layer.addTo(map)
	app.chooseMarker(app.current_pid)
}

async function fetchMarks() {
	if (map.getZoom() < 7) {
		app.zoom_in = true;
		marker_layer.remove();
		return;
	}
	app.zoom_in = false;
	let response = await fetch("https://bmserver.cole.ws/"+map.getBounds().toBBoxString());

	app.geojson = await response.json();
	app.shown_benchmarks = app.geojson.features.map((i)=>i.properties).sort((a,b)=>parseFloat(b.dec_lat)-parseFloat(a.dec_lat))

	refreshMap(app.geojson)
}

window.onload = function () {
	map = L.map('map', {preferCanvas:true}).setView([47.53945544742392,-120.70678710937501], 6);
	L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
		maxZoom: 19,
		attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
	}).addTo(map);

	fetchMarks()
	map.on("moveend", fetchMarks)
	setTimeout(() => {
		let pid = location.hash.substring(1);
		app.chooseMarker(pid);
		map.setView(app.markers[pid].getLatLng())
	}, 1000);
}
window.onhashchange = function() {
	let pid = location.hash.substring(1);
	app.chooseMarker(pid);
	map.setView(app.markers[pid].getLatLng());
}

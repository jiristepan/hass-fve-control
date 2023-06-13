# curl -X POST -H "Content-Type: application/json" \
#      -d '{"hass_name": "test", "hass_location_lat": "lat", "hass_location_lon":"lon", "data":{"a":1, "b":"a"}}' \
#      http://127.0.0.1:8080/fve_update

curl -X POST -H "Content-Type: application/json" \
     -d '{"hass_name": "test", "hass_location_lat": "lat", "hass_location_lon":"lon", "data":[{"a":1, "b":"a"}]}' \
     https://europe-west1-fve-control.cloudfunctions.net/fve_decisions
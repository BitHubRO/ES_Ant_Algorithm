# Romania map data

These files are bundled for offline educational visualization. Runtime map
loading makes no network requests. Coordinates are approximate city locations,
not street addresses. The boundary layer represents 2017 administrative units.

## County boundaries

`romania_counties.geojson` is the unmodified simplified geoBoundaries gbOpen
ROU ADM1 layer, boundary ID `ROU-ADM1-36066543`, 42 units (counties and București).
Source: World Bank via geoBoundaries, CC BY 4.0.

- Metadata: https://www.geoboundaries.org/api/current/gbOpen/ROU/ADM1/
- Pinned file: https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/9469f09/releaseData/gbOpen/ROU/ADM1/geoBoundaries-ROU-ADM1_simplified.geojson
- License: https://creativecommons.org/licenses/by/4.0/

## County seats

`romania_seats.json` contains 41 distinct locations, one per county seat.
București represents Ilfov's seat and the capital as a single marker, rather
than duplicating identical coordinates. County codes are stable marker IDs.

Coordinates for 40 cities were extracted from GeoNames `cities15000.zip`
(Romania PPLA/PPLC records plus Deva, ID 679452). GeoNames IDs are retained.
Names were normalized to modern Romanian ș/ț, and Bucharest is displayed as
București. The download's administrative-capital flags are not used at runtime.
County labels and codes were assigned explicitly rather than inferred from
population or geographic proximity.

- GeoNames download and data description: https://download.geonames.org/export/dump/
- GeoNames attribution and CC BY license: https://www.geonames.org/export/
- Călărași was absent from the downloaded cities15000 subset. Its approximate
  coordinates (44°12′ N, 27°21′ E) were added from Călărași council's document:
  https://www.calarasi.ro/wp-content/uploads/2024/05/HOTARAREA-9.pdf
- Ilfov council confirms its seat is București:
  https://cjilfov.ro/wp-content/uploads/Planul_de_men%C8%9Binere_a_calit%C4%83%C8%9Bii_aerului_Jud.Ilfov_2019-2023/PMCA-FINAL-ILFOV.pdf
- Deva municipality identifies Deva as Hunedoara's seat:
  https://www.primariadeva.ro/images/uploads/rapoarte/raport_anual.pdf
- Miercurea-Ciuc municipality identifies its city as Harghita's seat:
  https://miercureaciuc.ro/ro/istoria-orasului

Selection does not change the boundary extent. Drawing uses a local
equirectangular projection with longitude scaled by cos(46°). Tour costs use
the Haversine formula and mean Earth radius 6371.0088 km; they are geographic
distances, not driving distances. Lines connect city markers schematically.

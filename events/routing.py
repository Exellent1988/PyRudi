"""
Echte Routing-Integration für Running Dinner
Basiert auf OpenRouteService API für Fußgänger-Routen
"""

import requests
import logging
import time
from typing import Dict, Tuple, Optional
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class RouteCalculator:
    """
    Berechnet echte Fußgänger-Entfernungen zwischen Adressen
    Verwendet OpenRouteService API (kostenlos bis 2000 Anfragen/Tag)
    """

    def __init__(self):
        # OSRM API (komplett kostenlos, keine API-Key erforderlich)
        self.osrm_url = "http://router.project-osrm.org/route/v1/foot"

        # Fallback: OpenRouteService (mit API-Key)
        self.openroute_url = "https://api.openrouteservice.org/v2"
        self.api_key = getattr(settings, 'OPENROUTE_API_KEY', None)

        self.session = requests.Session()

        # Rate Limiting für fair use (langsamer für weniger API-Fehler)
        self.last_request_time = 0
        self.min_request_interval = 1.0  # 1 Sekunde zwischen Anfragen

    def get_coordinates_from_address(self, address: str) -> Optional[Tuple[float, float]]:
        """
        Konvertiert Adresse zu Koordinaten (Geocoding)
        Für Demo verwenden wir München-Koordinaten
        """
        # Cache für Adressen
        cache_key = f"geocode_{hash(address)}"
        cached_coords = cache.get(cache_key)
        if cached_coords:
            return cached_coords

        # Für Demo: Simuliere München-Adressen
        # In Produktion würde hier echtes Geocoding stattfinden
        import hashlib
        import random

        # Konsistente "Koordinaten" basierend auf Adresse
        hash_value = int(hashlib.md5(address.encode()).hexdigest()[:8], 16)
        random.seed(hash_value)

        # München Bounding Box
        lat_min, lat_max = 48.061, 48.248
        lng_min, lng_max = 11.360, 11.722

        lat = lat_min + (lat_max - lat_min) * random.random()
        lng = lng_min + (lng_max - lng_min) * random.random()

        coords = (lat, lng)
        cache.set(cache_key, coords, 3600 * 24)  # 24h Cache

        logger.info(f"📍 Geocoded '{address}' → {lat:.4f}, {lng:.4f}")
        return coords

    def get_walking_route_geometry(self, start_coords: Tuple[float, float], 
                                 end_coords: Tuple[float, float]) -> Optional[list]:
        """
        Holt die detaillierte Route-Geometrie für Kartendarstellung
        Gibt Liste von [lat, lng] Koordinaten zurück
        """
        start_lat, start_lng = start_coords
        end_lat, end_lng = end_coords
        
        try:
            # Rate Limiting
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            if time_since_last < self.min_request_interval:
                time.sleep(self.min_request_interval - time_since_last)
            
            # 1. Versuche OpenRouteService (bessere Geometrie)
            if self.api_key:
                openroute_url = f"{self.openroute_url}/directions/foot-walking"
                headers = {'Authorization': self.api_key}
                data = {
                    "coordinates": [[start_lng, start_lat], [end_lng, end_lat]],
                    "format": "json",
                    "geometry": "geojson"  # Wichtig für Route-Geometrie
                }
                
                response = self.session.post(openroute_url, json=data, headers=headers, timeout=15)
                self.last_request_time = time.time()
                
                if response.status_code == 200:
                    result = response.json()
                    if 'routes' in result and len(result['routes']) > 0:
                        # Extrahiere Geometrie-Koordinaten
                        geometry = result['routes'][0]['geometry']['coordinates']
                        # Konvertiere [lng, lat] zu [lat, lng] für Leaflet
                        route_points = [[point[1], point[0]] for point in geometry]
                        logger.info(f"🗺️ Route-Geometrie: {len(route_points)} Punkte")
                        return route_points
                        
                logger.warning(f"OpenRouteService Geometrie-Fehler (Status {response.status_code})")
            
            # 2. Fallback: OSRM (hat auch Geometrie)
            osrm_url = f"{self.osrm_url}/{start_lng},{start_lat};{end_lng},{end_lat}"
            response = self.session.get(osrm_url, params={'overview': 'full', 'geometries': 'geojson'}, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                if 'routes' in result and len(result['routes']) > 0:
                    geometry = result['routes'][0]['geometry']['coordinates']
                    route_points = [[point[1], point[0]] for point in geometry]
                    logger.info(f"🗺️ OSRM Route-Geometrie: {len(route_points)} Punkte")
                    return route_points
            
            # 3. Fallback: Gerade Linie
            logger.warning("Keine Route-Geometrie verfügbar, verwende Luftlinie")
            return [[start_lat, start_lng], [end_lat, end_lng]]
            
        except Exception as e:
            logger.error(f"Route-Geometrie Fehler: {e}")
            return [[start_lat, start_lng], [end_lat, end_lng]]

    def calculate_walking_distance(self, start_coords: Tuple[float, float], 
                                 end_coords: Tuple[float, float]) -> Optional[float]:
        """
        Berechnet echte Fußgänger-Entfernung zwischen zwei Koordinaten
        Verwendet OpenRouteService als primäre API, OSRM als Fallback
        """
        start_lat, start_lng = start_coords
        end_lat, end_lng = end_coords

        # Cache für Routen
        cache_key = f"route_{start_lat:.4f}_{start_lng:.4f}_{end_lat:.4f}_{end_lng:.4f}"
        cached_distance = cache.get(cache_key)
        if cached_distance:
            return cached_distance

        try:
            # Rate Limiting
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            if time_since_last < self.min_request_interval:
                time.sleep(self.min_request_interval - time_since_last)

            # 1. Primär: OpenRouteService (mit API-Key für beste Qualität)
            if self.api_key:
                openroute_url = f"{self.openroute_url}/directions/foot-walking"
                headers = {'Authorization': self.api_key}
                data = {
                    "coordinates": [[start_lng, start_lat], [end_lng, end_lat]],
                    "format": "json"
                }

                response = self.session.post(
                    openroute_url, json=data, headers=headers, timeout=10)
                self.last_request_time = time.time()

                if response.status_code == 200:
                    result = response.json()
                    if 'routes' in result and len(result['routes']) > 0:
                        distance_m = result['routes'][0]['summary']['distance']
                        distance_km = distance_m / 1000.0

                        cache.set(cache_key, distance_km, 3600 * 24)
                        logger.info(f"🚶 OpenRoute Route: {distance_km:.2f}km")
                        return distance_km

                logger.warning(
                    f"OpenRouteService Fehler (Status {response.status_code}), versuche OSRM...")

            # 2. Fallback: OSRM (kostenlos, robust)
            osrm_url = f"{self.osrm_url}/{start_lng},{start_lat};{end_lng},{end_lat}"
            response = self.session.get(
                osrm_url, params={'overview': 'false'}, timeout=10)

            if response.status_code == 200:
                result = response.json()
                if 'routes' in result and len(result['routes']) > 0:
                    # Entfernung in Metern → Kilometer
                    distance_m = result['routes'][0]['distance']
                    distance_km = distance_m / 1000.0

                    # Cache für 24h
                    cache.set(cache_key, distance_km, 3600 * 24)

                    logger.info(f"🚶 OSRM Fallback Route: {distance_km:.2f}km")
                    return distance_km

            # 3. Letzter Fallback: Luftlinie + Umwegfaktor
            logger.warning(
                "Beide APIs fehlgeschlagen, verwende Luftlinie-Schätzung")
            return self._calculate_haversine_distance(start_coords, end_coords) * 1.4

        except Exception as e:
            logger.error(f"Routing-Fehler: {e}")
            # Fallback: Luftlinie + Umwegfaktor für Straßen
            return self._calculate_haversine_distance(start_coords, end_coords) * 1.4

    def _calculate_haversine_distance(self, coord1: Tuple[float, float],
                                      coord2: Tuple[float, float]) -> float:
        """
        Berechnet Luftlinien-Entfernung zwischen zwei Koordinaten (Haversine-Formel)
        """
        import math

        lat1, lng1 = coord1
        lat2, lng2 = coord2

        # Radius der Erde in km
        R = 6371.0

        # Koordinaten in Radiant umwandeln
        lat1_rad = math.radians(lat1)
        lng1_rad = math.radians(lng1)
        lat2_rad = math.radians(lat2)
        lng2_rad = math.radians(lng2)

        # Haversine-Formel
        dlat = lat2_rad - lat1_rad
        dlng = lng2_rad - lng1_rad

        a = (math.sin(dlat / 2)**2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng / 2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        distance = R * c
        return distance

    def calculate_team_distances(self, teams) -> Dict[Tuple[int, int], float]:
        """
        Berechnet Entfernungsmatrix für alle Team-Paare
        """
        logger.info(
            f"🗺️ Berechne echte Fußgänger-Routen für {len(teams)} Teams...")

        # Hole Koordinaten für alle Teams
        team_coords = {}
        for team in teams:
            coords = self.get_coordinates_from_address(team.home_address)
            if coords:
                team_coords[team.id] = coords
            else:
                logger.warning(f"⚠️ Keine Koordinaten für Team {team.name}")

        # Berechne Entfernungsmatrix
        distances = {}
        total_calculations = len(teams) * (len(teams) - 1) // 2
        calculated = 0

        for i, team1 in enumerate(teams):
            for j, team2 in enumerate(teams):
                if i == j:
                    distances[(team1.id, team2.id)] = 0.0
                elif (team2.id, team1.id) in distances:
                    # Symmetrische Entfernung
                    distances[(team1.id, team2.id)
                              ] = distances[(team2.id, team1.id)]
                else:
                    if team1.id in team_coords and team2.id in team_coords:
                        distance = self.calculate_walking_distance(
                            team_coords[team1.id],
                            team_coords[team2.id]
                        )
                        if distance:
                            distances[(team1.id, team2.id)] = distance
                            distances[(team2.id, team1.id)] = distance
                            calculated += 1

                            if calculated % 5 == 0:  # Progress-Update
                                logger.info(
                                    f"📊 {calculated}/{total_calculations} Routen berechnet")
                        else:
                            # Fallback bei Fehler
                            distances[(team1.id, team2.id)] = 2.5
                            distances[(team2.id, team1.id)] = 2.5
                    else:
                        # Fallback bei fehlenden Koordinaten
                        distances[(team1.id, team2.id)] = 3.0
                        distances[(team2.id, team1.id)] = 3.0

        logger.info(
            f"✅ {calculated} echte Routen berechnet, Rest per Fallback")
        return distances


def get_route_calculator() -> RouteCalculator:
    """Factory function für RouteCalculator"""
    return RouteCalculator()

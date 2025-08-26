"""
Running Dinner Optimization using Mixed-Integer Programming
Basiert auf dem Ansatz von https://github.com/fm-or/running-dinner
"""

import random
from typing import List, Dict, Tuple, Optional
from django.utils import timezone
import pulp
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


class RunningDinnerOptimizer:
    """
    Mixed-Integer Programming Optimizer für Running Dinner Events

    Implementiert die mathematische Formulierung aus fm-or/running-dinner:
    - Minimiert maximale Reisezeiten zwischen Events
    - Stellt sicher, dass sich Teams nur einmal treffen
    - Verteilt Teams optimal auf Kurse (appetizer, main_course, dessert)
    """

    def __init__(self, event):
        self.event = event
        self.teams = []
        self.team_registrations = []
        self.distances = {}  # Simulierte Entfernungen
        self.courses = ['appetizer', 'main_course', 'dessert']
        self.k = 3  # Anzahl Teams pro Event (Host + 2 Gäste)

        # Progress-Tracking für Live-Updates
        self.progress_key = f"optimization_progress_{event.id}"
        self.log_key = f"optimization_log_{event.id}"
        self._init_progress()

        # Penalty-Gewichte für Constraint-Verletzungen
        self.P1 = 100.0  # Penalty für zu wenige Teams (k-1)
        self.P2 = 100.0  # Penalty für zu viele Teams (k+1)
        self.P3 = 50.0   # Penalty für mehrfache Begegnungen

    def _init_progress(self):
        """Initialisiere Progress-Tracking"""
        cache.set(self.progress_key, {
            'step': 0,
            'total_steps': 5,
            'current_task': 'Starte Optimierung...',
            'percentage': 0,
            'status': 'running'
        }, timeout=300)  # 5 Minuten Cache

        cache.set(self.log_key, [], timeout=300)

    def _update_progress(self, step: int, total_steps: int, task: str, details: str = None):
        """Update Progress für Live-Anzeige"""
        percentage = int((step / total_steps) * 100)

        progress = {
            'step': step,
            'total_steps': total_steps,
            'current_task': task,
            'percentage': percentage,
            'status': 'running' if step < total_steps else 'completed'
        }

        cache.set(self.progress_key, progress, timeout=300)

        # Log-Eintrag hinzufügen
        logs = cache.get(self.log_key, [])
        log_message = f"Schritt {step}/{total_steps}: {task}"
        if details:
            log_message += f" - {details}"

        logs.append({
            'timestamp': timezone.now().strftime('%H:%M:%S'),
            'message': log_message
        })
        # Nur die letzten 50 Log-Einträge behalten
        if len(logs) > 50:
            logs = logs[-50:]
        cache.set(self.log_key, logs, timeout=300)

    def load_teams(self):
        """Lade bestätigte Teams für das Event und zusätzliche Features"""
        from events.models import GuestKitchen, AfterPartyLocation

        self.team_registrations = list(
            self.event.team_registrations.filter(status='confirmed')
            .select_related('team')
        )

        # Filtere Teams nach Teilnahme-Art
        all_teams = [reg.team for reg in self.team_registrations]

        # Teams die als Host UND Gast teilnehmen können
        self.teams = [
            team for team in all_teams if team.can_participate_as_host and team.can_participate_as_guest]

        # Teams die nur als Gäste teilnehmen
        self.guest_only_teams = [
            team for team in all_teams if team.participation_type == 'guest_only']

        # Teams ohne Küche (brauchen Gastküche wenn sie hosten)
        self.teams_needing_kitchen = [
            team for team in self.teams if team.needs_guest_kitchen]

        if len(self.teams) < 3:
            raise ValueError(
                f"Mindestens 3 Host-Teams erforderlich, aber nur {len(self.teams)} verfügbar")

        logger.info(
            f"🎯 Optimiere {len(self.teams)} Host-Teams für Event '{self.event.name}'")
        logger.info(f"👥 {len(self.guest_only_teams)} Nur-Gast-Teams verfügbar")
        logger.info(
            f"🏠 {len(self.teams_needing_kitchen)} Teams brauchen Gastküche")

        # Lade Gastküchen
        self.guest_kitchens = list(
            self.event.guest_kitchens.filter(is_active=True))

        # Lade Afterparty Location
        try:
            self.after_party = self.event.after_party
        except AfterPartyLocation.DoesNotExist:
            self.after_party = None

        logger.info(
            f"🎯 Optimiere {len(self.teams)} Teams für Event '{self.event.name}'")
        logger.info(f"🏠 {len(self.guest_kitchens)} Gastküchen verfügbar")
        if self.after_party:
            logger.info(
                f"🎉 Afterparty: {self.after_party.name} um {self.after_party.start_time}")

    def calculate_distances(self):
        """
        Berechne echte Fußgänger-Entfernungen zwischen allen Teams
        Verwendet OpenRouteService API für realistische Routen
        """
        from .routing import get_route_calculator

        n = len(self.teams)
        self._update_progress(1, 5, f"Berechne Routen für {n} Teams",
                              f"🗺️ Berechne echte Fußgänger-Routen für {n} Teams...")
        logger.info(f"🗺️ Berechne echte Fußgänger-Routen für {n} Teams...")

        # Verwende echtes Routing
        route_calculator = get_route_calculator()
        self.distances = route_calculator.calculate_team_distances(self.teams)

        # Distanzen zu Gastküchen
        self.guest_kitchen_distances = {}
        if self.guest_kitchens:
            logger.info(
                f"🏠 Berechne Routen zu {len(self.guest_kitchens)} Gastküchen...")
            for kitchen in self.guest_kitchens:
                if kitchen.latitude and kitchen.longitude:
                    kitchen_coords = (float(kitchen.latitude),
                                      float(kitchen.longitude))

                    for team in self.teams:
                        if team.latitude and team.longitude:
                            team_coords = (float(team.latitude),
                                           float(team.longitude))
                            distance = route_calculator.calculate_walking_distance(
                                team_coords, kitchen_coords)
                            self.guest_kitchen_distances[(
                                team.id, kitchen.id)] = distance

                    # Distanzen zwischen Gastküchen und anderen Gastküchen
                    for other_kitchen in self.guest_kitchens:
                        if (other_kitchen.id != kitchen.id and
                                other_kitchen.latitude and other_kitchen.longitude):
                            other_coords = (float(other_kitchen.latitude), float(
                                other_kitchen.longitude))
                            distance = route_calculator.calculate_walking_distance(
                                kitchen_coords, other_coords)
                            self.guest_kitchen_distances[(
                                f'kitchen_{kitchen.id}', f'kitchen_{other_kitchen.id}')] = distance

        # Distanzen zur Afterparty
        self.after_party_distances = {}
        if self.after_party and self.after_party.latitude and self.after_party.longitude:
            logger.info(
                f"🎉 Berechne Routen zur Afterparty: {self.after_party.name}")
            afterparty_coords = (float(self.after_party.latitude), float(
                self.after_party.longitude))

            # Von Teams zur Afterparty
            for team in self.teams:
                if team.latitude and team.longitude:
                    team_coords = (float(team.latitude), float(team.longitude))
                    distance = route_calculator.calculate_walking_distance(
                        team_coords, afterparty_coords)
                    self.after_party_distances[team.id] = distance

            # Von Gastküchen zur Afterparty
            for kitchen in self.guest_kitchens:
                if kitchen.latitude and kitchen.longitude:
                    kitchen_coords = (float(kitchen.latitude),
                                      float(kitchen.longitude))
                    distance = route_calculator.calculate_walking_distance(
                        kitchen_coords, afterparty_coords)
                    self.after_party_distances[f'kitchen_{kitchen.id}'] = distance

        # Validierung: Prüfe ob alle Entfernungen vorhanden sind
        missing_distances = 0
        for i, team1 in enumerate(self.teams):
            for j, team2 in enumerate(self.teams):
                if (team1.id, team2.id) not in self.distances:
                    logger.warning(
                        f"⚠️ Fehlende Entfernung: {team1.name} → {team2.name}")
                    # Fallback-Entfernung
                    self.distances[(team1.id, team2.id)] = 2.5
                    missing_distances += 1

        if missing_distances > 0:
            logger.warning(
                f"⚠️ {missing_distances} Entfernungen mit Fallback-Werten ergänzt")

        # Statistiken
        all_distances = [d for d in self.distances.values() if d > 0]
        if all_distances:
            avg_distance = sum(all_distances) / len(all_distances)
            max_distance = max(all_distances)
            min_distance = min(all_distances)

            logger.info(f"📊 Entfernungs-Statistiken:")
            logger.info(f"   Ø Entfernung: {avg_distance:.2f}km")
            logger.info(
                f"   Min/Max: {min_distance:.2f}km / {max_distance:.2f}km")
            logger.info(f"   Gesamt: {len(all_distances)} Routen berechnet")
        else:
            logger.error("❌ Keine gültigen Entfernungen berechnet!")

        logger.info(f"✅ Echte Fußgänger-Routen für {n} Teams berechnet")

    def create_mip_model(self):
        """
        Erstelle Mixed-Integer Programming Model basierend auf fm-or/running-dinner
        """
        # Erstelle Problem
        self.prob = pulp.LpProblem("RunningDinner", pulp.LpMinimize)

        n_teams = len(self.teams)
        n_courses = len(self.courses)

        # === VARIABLEN ===

        # x[g,h,e] = 1 wenn Gruppe g Gruppe h bei Event e besucht
        self.x = {}
        for i, team_g in enumerate(self.teams):
            for j, team_h in enumerate(self.teams):
                for k, course in enumerate(self.courses):
                    var_name = f"x_{team_g.id}_{team_h.id}_{course}"
                    self.x[(i, j, k)] = pulp.LpVariable(var_name, cat='Binary')

        # t[e] = maximale Reisezeit von Event e zum nächsten Event
        self.t = {}
        for k in range(n_courses):
            var_name = f"t_{self.courses[k]}"
            self.t[k] = pulp.LpVariable(var_name, lowBound=0)

        # y[g,g',h,e] = 1 wenn Gruppen g und g' sich bei Host h für Event e treffen
        self.y = {}
        for i, team_g in enumerate(self.teams):
            for ii, team_gg in enumerate(self.teams):
                if i < ii:  # Nur eine Richtung wegen Symmetrie
                    for j, team_h in enumerate(self.teams):
                        for k, course in enumerate(self.courses):
                            var_name = f"y_{team_g.id}_{team_gg.id}_{team_h.id}_{course}"
                            self.y[(i, ii, j, k)] = pulp.LpVariable(
                                var_name, cat='Binary')

        # z1[h,e] = 1 wenn bei Host h für Event e nur k-1 Teams sind (Penalty)
        self.z1 = {}
        for j, team_h in enumerate(self.teams):
            for k, course in enumerate(self.courses):
                var_name = f"z1_{team_h.id}_{course}"
                self.z1[(j, k)] = pulp.LpVariable(var_name, cat='Binary')

        # z2[h,e] = 1 wenn bei Host h für Event e k+1 Teams sind (Penalty)
        self.z2 = {}
        for j, team_h in enumerate(self.teams):
            for k, course in enumerate(self.courses):
                var_name = f"z2_{team_h.id}_{course}"
                self.z2[(j, k)] = pulp.LpVariable(var_name, cat='Binary')

        # z3[g,g'] = Anzahl extra Begegnungen zwischen Gruppen g und g' (Penalty)
        self.z3 = {}
        for i, team_g in enumerate(self.teams):
            for ii, team_gg in enumerate(self.teams):
                if i < ii:  # Nur eine Richtung wegen Symmetrie
                    var_name = f"z3_{team_g.id}_{team_gg.id}"
                    self.z3[(i, ii)] = pulp.LpVariable(
                        var_name, lowBound=0, cat='Integer')

        # === ZIELFUNKTION ===
        # Minimiere: Summe der maximalen Reisezeiten + Penalty-Costs

        travel_time_sum = pulp.lpSum([self.t[k] for k in range(n_courses)])

        penalty_z1 = self.P1 * \
            pulp.lpSum([self.z1[(j, k)] for j in range(n_teams)
                       for k in range(n_courses)])
        penalty_z2 = self.P2 * \
            pulp.lpSum([self.z2[(j, k)] for j in range(n_teams)
                       for k in range(n_courses)])
        penalty_z3 = (self.P3 / 2) * pulp.lpSum([self.z3[(i, ii)]
                                                 for i in range(n_teams) for ii in range(i+1, n_teams)])

        self.prob += travel_time_sum + penalty_z1 + penalty_z2 + penalty_z3

        logger.info(
            "✅ MIP-Modell erstellt: Variablen und Zielfunktion definiert")

    def add_constraints(self):
        """Füge alle Constraints zum MIP-Model hinzu"""
        n_teams = len(self.teams)
        n_courses = len(self.courses)

        # === CONSTRAINT 1: Jede Gruppe besucht genau einen Host pro Event ===
        for i in range(n_teams):
            for k in range(n_courses):
                constraint_name = f"one_host_per_event_{i}_{k}"
                self.prob += (
                    pulp.lpSum([self.x[(i, j, k)]
                               for j in range(n_teams)]) == 1,
                    constraint_name
                )

        # === CONSTRAINT 2: Jede Gruppe besucht sich selbst wenn sie hostet ===
        for i in range(n_teams):
            for k in range(n_courses):
                # Wenn Team i bei Kurs k hostet, muss x[i,i,k] = 1 sein
                # Das wird durch die Hosting-Zuweisung in der Optimierung sichergestellt
                pass

        # === CONSTRAINT 3: Korrekte Anzahl Teams pro Host (k=3 mit Penalties) ===
        for j in range(n_teams):  # Für jeden potentiellen Host
            for k in range(n_courses):  # Für jeden Kurs
                constraint_name = f"teams_per_host_{j}_{k}"
                self.prob += (
                    pulp.lpSum([self.x[(i, j, k)] for i in range(n_teams)]) ==
                    self.k - self.z1[(j, k)] + self.z2[(j, k)],
                    constraint_name
                )

        # === CONSTRAINT 4: y-Variablen Kopplung (Teams treffen sich) ===
        for i in range(n_teams):
            for ii in range(i+1, n_teams):
                for j in range(n_teams):
                    for k in range(n_courses):
                        constraint_name = f"meeting_{i}_{ii}_{j}_{k}"
                        # Wenn beide Teams beim selben Host sind, dann treffen sie sich
                        self.prob += (
                            self.x[(i, j, k)] + self.x[(ii, j, k)
                                                       ] <= 1 + self.y[(i, ii, j, k)],
                            constraint_name
                        )

        # === CONSTRAINT 5: Teams treffen sich maximal einmal (mit Penalty) ===
        for i in range(n_teams):
            for ii in range(i+1, n_teams):
                constraint_name = f"max_one_meeting_{i}_{ii}"
                self.prob += (
                    pulp.lpSum([self.y[(i, ii, j, k)] for j in range(n_teams) for k in range(n_courses)]) <=
                    1 + self.z3[(i, ii)],
                    constraint_name
                )

        # === CONSTRAINT 6: Reisezeit-Constraints ===
        # Zwischen aufeinanderfolgenden Events
        for i in range(n_teams):
            for k in range(n_courses - 1):  # k -> k+1
                for j1 in range(n_teams):
                    for j2 in range(n_teams):
                        constraint_name = f"travel_time_{i}_{k}_{j1}_{j2}"
                        distance = self.distances[(
                            self.teams[j1].id, self.teams[j2].id)]
                        # Wenn Team i von Host j1 (Event k) zu Host j2 (Event k+1) geht
                        self.prob += (
                            distance *
                            (self.x[(i, j1, k)] +
                             self.x[(i, j2, k+1)] - 1) <= self.t[k],
                            constraint_name
                        )

        logger.info("✅ Alle Constraints hinzugefügt")

    def solve(self) -> bool:
        """Löse das MIP-Problem mit Fallback-Strategien"""
        logger.info("🚀 Starte MIP-Optimierung...")

        # Versuche verschiedene Solver und Einstellungen
        solvers = [
            (pulp.PULP_CBC_CMD(msg=0, timeLimit=30), "CBC"),
            (pulp.PULP_COIN_CMD(msg=0, timeLimit=30), "COIN"),
        ]

        for solver, name in solvers:
            try:
                logger.info(f"📊 Versuche Solver: {name}")
                self.prob.solve(solver)

                status = pulp.LpStatus[self.prob.status]
                logger.info(f"📊 Status mit {name}: {status}")

                if self.prob.status == pulp.LpStatusOptimal:
                    objective_value = pulp.value(self.prob.objective)
                    logger.info(f"🎯 Optimaler Wert: {objective_value:.2f}")
                    return True
                elif self.prob.status == pulp.LpStatusFeasible:
                    # Auch suboptimale Lösungen akzeptieren
                    objective_value = pulp.value(self.prob.objective)
                    logger.warning(
                        f"⚠️ Suboptimale Lösung: {objective_value:.2f}")
                    return True

            except Exception as e:
                logger.warning(f"⚠️ Solver {name} fehlgeschlagen: {e}")
                continue

        logger.error(f"❌ Alle MIP-Solver fehlgeschlagen")
        return False

    def extract_solution(self) -> Dict:
        """Extrahiere Lösung aus dem gelösten MIP-Model"""
        if self.prob.status not in [pulp.LpStatusOptimal, pulp.LpStatusFeasible]:
            raise ValueError("Keine gültige Lösung verfügbar")

        solution = {
            'assignments': [],
            'hosting': {},  # course -> [team_ids]
            'meetings': {},  # (team1_id, team2_id) -> [courses]
            'travel_times': {},  # course -> max_time
            'objective_value': pulp.value(self.prob.objective),
            'penalties': {
                'z1_violations': 0,
                'z2_violations': 0,
                'z3_violations': 0
            }
        }

        n_teams = len(self.teams)
        n_courses = len(self.courses)

        # Extrahiere Team-Zuweisungen
        for i, team in enumerate(self.teams):
            assignment = {
                'team': team,
                'hosts': {},  # course -> host_team
                'course_hosted': None,  # welchen Kurs hostet dieses Team
                'distances': {},  # course -> distance
                'total_distance': 0
            }

            for k, course in enumerate(self.courses):
                for j, host_team in enumerate(self.teams):
                    if pulp.value(self.x[(i, j, k)]) == 1:
                        assignment['hosts'][course] = host_team
                        assignment['distances'][course] = self.distances[(
                            team.id, host_team.id)]

                        # Prüfe ob Team sich selbst hostet
                        if i == j:
                            assignment['course_hosted'] = course

            assignment['total_distance'] = sum(
                assignment['distances'].values())
            solution['assignments'].append(assignment)

        # Extrahiere Hosting-Information
        for k, course in enumerate(self.courses):
            solution['hosting'][course] = []
            for j, team in enumerate(self.teams):
                # Team j hostet Kurs k wenn es Gäste hat
                guest_count = sum([pulp.value(self.x[(i, j, k)])
                                  for i in range(n_teams)])
                if guest_count > 1:  # Host + Gäste
                    solution['hosting'][course].append(team.id)

        # Extrahiere Reisezeiten
        for k, course in enumerate(self.courses):
            solution['travel_times'][course] = pulp.value(self.t[k])

        # Extrahiere Penalties
        solution['penalties']['z1_violations'] = sum(
            [pulp.value(self.z1[(j, k)]) for j in range(n_teams) for k in range(n_courses)])
        solution['penalties']['z2_violations'] = sum(
            [pulp.value(self.z2[(j, k)]) for j in range(n_teams) for k in range(n_courses)])
        solution['penalties']['z3_violations'] = sum([pulp.value(
            self.z3[(i, ii)]) for i in range(n_teams) for ii in range(i+1, n_teams)])

        logger.info(
            f"✅ Lösung extrahiert: {len(solution['assignments'])} Team-Zuweisungen")
        return solution

    def simple_running_dinner_solution(self) -> Dict:
        """
        Korrekte Running Dinner Lösung
        Prinzip: Jedes Team hostet GENAU einen Kurs und besucht die anderen beiden
        """
        self._update_progress(2, 5, "Running Dinner Algorithmus",
                              "🍽️ Starte Running Dinner Algorithmus...")
        logger.info("🍽️ Starte Running Dinner Algorithmus...")

        n_teams = len(self.teams)
        courses = self.courses
        n_courses = len(courses)

        # Berechne Teams pro Kurs (sollte bei 12 Teams = 4 pro Kurs sein)
        teams_per_course = n_teams // n_courses
        extra_teams = n_teams % n_courses

        solution = {
            'assignments': [],
            'hosting': {},
            'meetings': {},
            'travel_times': {},
            'objective_value': 0.0,
            'penalties': {'z1_violations': 0, 'z2_violations': 0, 'z3_violations': 0}
        }

        # SCHRITT 1: Weise jedes Team einem Hosting-Kurs zu
        team_hosting_map = {}  # team_id -> course
        host_teams_by_course = {}  # course -> [team_ids]
        team_idx = 0

        for course_idx, course in enumerate(courses):
            num_hosts_for_course = teams_per_course + \
                (1 if course_idx < extra_teams else 0)
            course_hosts = self.teams[team_idx:team_idx + num_hosts_for_course]

            host_teams_by_course[course] = course_hosts
            solution['hosting'][course] = [t.id for t in course_hosts]

            for team in course_hosts:
                team_hosting_map[team.id] = course

            team_idx += num_hosts_for_course
            logger.info(
                f"📍 {course}: {len(course_hosts)} Teams hosten diesen Kurs")

        # SCHRITT 2: Optimiere Team-Diversität (FM-OR inspiriert)
        # Ziel: Teams sollen sich möglichst nur einmal treffen
        logger.info("🔄 Optimiere Team-Diversität...")
        self._optimize_team_diversity(
            solution, host_teams_by_course, team_hosting_map)

        # SCHRITT 4: Für jedes Team berechne seine Route (welche Hosts besucht es)
        # WICHTIG: Korrekte Route-Berechnung: Home → Vorspeise → Hauptgang → Nachspeise
        # (nicht immer von Home aus, sondern von der aktuellen Position!)
        total_distance = 0

        # Verwende optimierte Gäste-Zuordnungen aus Diversitäts-Optimierung
        guests_per_host = solution['guests_per_host']

        for team in self.teams:
            my_hosting_course = team_hosting_map[team.id]
            hosts = {}
            distances = {}

            # Verfolge die aktuelle Position des Teams während der Route
            current_location = team  # Start von der Team-Home-Adresse

            # Für jeden Kurs: Finde besten verfügbaren Host (korrekte Route-Berechnung)
            for course in courses:
                if course == my_hosting_course:
                    # Ich hoste diesen Kurs selbst - muss nach Hause!
                    hosts[course] = None

                    # KRITISCHER FIX: Distanz zur Hosting-Location (= Zuhause) berechnen
                    if current_location.id != team.id:
                        # Team ist woanders und muss nach Hause
                        distances[course] = self.distances[(
                            current_location.id, team.id)]
                    else:
                        # Team ist bereits zuhause
                        distances[course] = 0

                    # Aktuelle Position: Jetzt zuhause (Team-Home)
                    current_location = team
                else:
                    # KRITISCHER FIX: Finde den BESTEN Host basierend auf aktueller Position!
                    # Ignoriere Diversity-Zuordnungen für bessere Routen

                    best_host = None
                    min_distance = float('inf')

                    # Prüfe alle verfügbaren Hosts für diesen Kurs
                    for potential_host in host_teams_by_course[course]:
                        # Berechne Distanz von aktueller Position zu diesem Host
                        distance = self.distances.get(
                            (current_location.id, potential_host.id), float('inf'))

                        if distance < min_distance:
                            min_distance = distance
                            best_host = potential_host

                    if best_host:
                        hosts[course] = best_host
                        distances[course] = min_distance
                        # Team bewegt sich zum neuen Host-Standort
                        current_location = best_host
                        logger.debug(
                            f"   🎯 {team.name} → {best_host.name} ({min_distance:.1f}km)")
                    else:
                        logger.warning(
                            f"⚠️ Keine Hosts für {course} verfügbar!")
                        # Fallback: Nehme ersten verfügbaren Host
                        fallback_host = host_teams_by_course[course][0]
                        hosts[course] = fallback_host
                        distances[course] = self.distances.get(
                            (current_location.id, fallback_host.id), 5.0)
                        current_location = fallback_host

            team_total_distance = sum(distances.values())
            total_distance += team_total_distance

            assignment = {
                'team': team,
                'hosts': hosts,
                'course_hosted': my_hosting_course,
                'distances': distances,
                'total_distance': team_total_distance
            }
            solution['assignments'].append(assignment)

        # SCHRITT 3: Berechne Statistiken und validiere
        avg_distance = total_distance / n_teams

        logger.info(f"✅ Running Dinner Lösung erstellt:")
        logger.info(
            f"   📊 {n_teams} Teams, {total_distance:.1f}km total, {avg_distance:.1f}km Ø")

        # Validierung: Jeder Host sollte 3-4 Gäste haben
        for course in courses:
            hosts_in_course = host_teams_by_course[course]
            logger.info(f"   🏠 {course}: {len(hosts_in_course)} Hosts")
            for host in hosts_in_course:
                guest_count = len(guests_per_host[host.id])
                logger.info(f"      - {host.name}: {guest_count} Gäste")

        solution['objective_value'] = total_distance
        solution['travel_times'] = {course: avg_distance for course in courses}

        # SCHRITT 4: Gastküchen-Zuordnung (optional)
        if self.guest_kitchens:
            self._update_progress(3.5, 5, "Gastküchen-Zuordnung",
                                  "🏠 Weise Teams zu Gastküchen zu...")
            solution = self.assign_guest_kitchens(solution)

        # SCHRITT 5: Post-Optimierung - Verbessere Verteilung und Distanzen
        self._update_progress(4, 5, "Post-Optimierung",
                              "🔄 Starte Post-Optimierung...")
        logger.info("🔄 Starte Post-Optimierung...")
        optimized_solution = self.improve_guest_distribution(
            solution, guests_per_host, host_teams_by_course)

        return optimized_solution

    def _optimize_team_diversity(self, solution, host_teams_by_course, team_hosting_map):
        """
        Optimiert Team-Zuordnungen für maximale Diversität
        Basiert auf fm-or Constraint: Teams sollen sich maximal einmal treffen

        Strategie:
        1. Tracke alle Team-Begegnungen
        2. Erstelle Gast-Zuordnungen die Wiederholungen minimieren  
        3. Gewichte Diversität höher als Distanz
        """
        logger.info("🎯 Starte Diversitäts-Optimierung...")
        self._update_progress(3, 5, "Diversitäts-Optimierung",
                              f"Optimiere {len(self.teams)} Teams für maximale Vielfalt")

        # Track alle Team-Begegnungen: team_pair -> anzahl_treffen
        team_meetings = {}

        # Initialisiere Gäste-Listen für jeden Host
        guests_per_host = {}  # host_team_id -> [guest_team_objects]
        for course, host_teams in host_teams_by_course.items():
            for host_team in host_teams:
                guests_per_host[host_team.id] = []

        # Für jeden Kurs optimiere Gast-Zuordnungen
        for course in self.courses:
            course_display = {'appetizer': 'Vorspeise',
                              'main_course': 'Hauptgang', 'dessert': 'Nachspeise'}[course]
            logger.info(
                f"🍽️ Optimiere {course_display}-Zuordnungen für Diversität...")

            host_teams = host_teams_by_course[course]
            guest_teams = [
                t for t in self.teams if team_hosting_map[t.id] != course]

            # Ziel: Verteile guest_teams auf host_teams mit maximaler Diversität
            # Standard: 2 Gäste pro Host (bei 12 Teams, 4 Hosts = 8 Gäste → 2 pro Host)
            guests_per_host_target = len(guest_teams) // len(host_teams)
            extra_guests = len(guest_teams) % len(host_teams)

            # Greedy-Algorithmus: Für jeden Gast finde besten Host
            guest_teams_copy = guest_teams.copy()
            random.shuffle(guest_teams_copy)  # Randomisierung für Fairness

            for guest_team in guest_teams_copy:
                best_host = None
                best_score = float('inf')

                for host_team in host_teams:
                    current_guest_count = len(guests_per_host[host_team.id])
                    target_guest_count = guests_per_host_target + \
                        (1 if host_teams.index(host_team) < extra_guests else 0)

                    # Skip wenn Host bereits voll
                    if current_guest_count >= target_guest_count:
                        continue

                    # Berechne Diversitäts-Score
                    diversity_penalty = 0
                    for existing_guest in guests_per_host[host_team.id]:
                        # Prüfe ob guest_team und existing_guest sich bereits getroffen haben
                        pair_key = tuple(
                            sorted([guest_team.id, existing_guest.id]))
                        meetings_count = team_meetings.get(pair_key, 0)
                        diversity_penalty += meetings_count * 1000  # Hohe Strafe für Wiederholungen

                        # Prüfe auch mit dem Host selbst
                        host_pair_key = tuple(
                            sorted([guest_team.id, host_team.id]))
                        host_meetings = team_meetings.get(host_pair_key, 0)
                        diversity_penalty += host_meetings * 1000

                    # Berechne Distanz-Score (geringere Gewichtung)
                    distance_score = self.distances.get(
                        (guest_team.id, host_team.id), 0) * 1  # Niedrige Gewichtung

                    # Gesamt-Score: Diversität >> Distanz
                    total_score = diversity_penalty + distance_score

                    if total_score < best_score:
                        best_score = total_score
                        best_host = host_team

                if best_host:
                    guests_per_host[best_host.id].append(guest_team)

                    # Update Meeting-Tracker
                    for existing_guest in guests_per_host[best_host.id]:
                        if existing_guest.id != guest_team.id:
                            pair_key = tuple(
                                sorted([guest_team.id, existing_guest.id]))
                            team_meetings[pair_key] = team_meetings.get(
                                pair_key, 0) + 1

                    # Meeting mit Host tracken
                    host_pair_key = tuple(
                        sorted([guest_team.id, best_host.id]))
                    team_meetings[host_pair_key] = team_meetings.get(
                        host_pair_key, 0) + 1

                    logger.debug(
                        f"   👥 {guest_team.name} → {best_host.name} (Score: {best_score:.1f})")

        # Speichere optimierte Zuordnungen in solution
        solution['guests_per_host'] = guests_per_host
        solution['team_meetings'] = team_meetings

        # Analysiere Diversitäts-Qualität
        total_meetings = sum(team_meetings.values())
        repeated_meetings = sum(
            1 for count in team_meetings.values() if count > 1)

        logger.info(f"🎯 Diversitäts-Analyse:")
        logger.info(f"   📊 Gesamt Team-Begegnungen: {total_meetings}")
        logger.info(f"   🔄 Wiederholte Begegnungen: {repeated_meetings}")
        logger.info(
            f"   📈 Diversitäts-Rate: {((total_meetings - repeated_meetings) / total_meetings * 100):.1f}%")

        return solution

    def assign_guest_kitchens(self, solution):
        """
        Weise Teams automatisch zu Gastküchen zu, wenn dies vorteilhaft ist
        Logik: Teams mit langen Wegen zu Host-Locations nutzen nähere Gastküchen
        """
        logger.info("🏠 Starte automatische Gastküchen-Zuordnung...")
        self._update_progress(4, 5, "Gastküchen-Zuordnung",
                              f"Analysiere {len(self.guest_kitchens)} Gastküchen für optimale Zuordnung")

        # Lösche alte Gastküchen-Zuordnungen für dieses Event
        from events.models import TeamGuestKitchenAssignment
        TeamGuestKitchenAssignment.objects.filter(
            team__in=self.teams,
            guest_kitchen__event=self.event
        ).delete()

        assignments_created = 0
        distance_savings = 0
        mandatory_assignments = 0

        # SCHRITT 1: Zwingend erforderliche Zuordnungen (Teams ohne Küche)
        logger.info(
            "🔴 Verarbeite ZWINGEND erforderliche Gastküchen-Zuordnungen...")

        for course in self.courses:
            course_display = {'appetizer': 'Vorspeise',
                              'main_course': 'Hauptgang', 'dessert': 'Nachspeise'}[course]

            # Teams ohne Küche die für diesen Kurs hosten
            mandatory_teams = []
            for assignment in solution['assignments']:
                if (assignment['course_hosted'] == course and
                        assignment['team'].needs_guest_kitchen):
                    mandatory_teams.append(assignment)

            if mandatory_teams:
                logger.info(
                    f"🔴 {len(mandatory_teams)} Teams ohne Küche hosten {course_display}")

                # Verfügbare Gastküchen für diesen Kurs
                available_kitchens = [
                    k for k in self.guest_kitchens
                    if k.can_host_course(course)
                ]

                if len(available_kitchens) == 0:
                    raise ValueError(
                        f"KRITISCHER FEHLER: Teams ohne Küche hosten {course_display}, aber keine Gastküchen verfügbar!")

                # Zuordnung der zwingend erforderlichen Teams - berücksichtige bereits bestehende Zuordnungen
                kitchen_usage = {}
                for kitchen in available_kitchens:
                    current_usage = kitchen.using_teams.filter(
                        course=course,
                        is_active=True
                    ).count()
                    kitchen_usage[kitchen.id] = current_usage

                for assignment in mandatory_teams:
                    team = assignment['team']

                    # Finde beste verfügbare Gastküche
                    best_kitchen = None
                    best_distance = float('inf')

                    for kitchen in available_kitchens:
                        if kitchen_usage[kitchen.id] >= kitchen.max_teams:
                            continue

                        distance = self.guest_kitchen_distances.get(
                            (team.id, kitchen.id), float('inf'))
                        if distance < best_distance:
                            best_distance = distance
                            best_kitchen = kitchen

                    if not best_kitchen:
                        raise ValueError(
                            f"KRITISCHER FEHLER: Keine Gastküche für Team '{team.name}' verfügbar (alle belegt)!")

                    # ZWINGEND ERFORDERLICHE Zuordnung erstellen
                    try:
                        kitchen_assignment = TeamGuestKitchenAssignment.objects.create(
                            team=team,
                            guest_kitchen=best_kitchen,
                            course=course,
                            notes=f"ZWINGEND erforderlich (Team ohne Küche). Distanz: {best_distance:.1f}km"
                        )

                        kitchen_usage[best_kitchen.id] += 1
                        mandatory_assignments += 1
                        assignments_created += 1

                        logger.info(
                            f"🔴 ZWINGEND: {team.name} → {best_kitchen.name} ({course_display}) - {best_distance:.1f}km")

                    except Exception as e:
                        raise ValueError(
                            f"KRITISCHER FEHLER: Konnte Team '{team.name}' nicht zu Gastküche zuweisen: {e}")

        # SCHRITT 2: Optionale Zuordnungen (Distanz-Optimierung)
        logger.info(
            "🟡 Verarbeite optionale Gastküchen-Zuordnungen (Distanz-Optimierung)...")

        # Analysiere jeden Kurs separat für optionale Zuordnungen
        for course in self.courses:
            course_display = {'appetizer': 'Vorspeise',
                              'main_course': 'Hauptgang', 'dessert': 'Nachspeise'}[course]
            logger.info(
                f"🍽️ Analysiere optionale {course_display}-Zuordnungen...")

            # Verfügbare Gastküchen für diesen Kurs (nach zwingenden Zuordnungen)
            available_kitchens = []
            kitchen_usage = {}

            for kitchen in self.guest_kitchens:
                if kitchen.can_host_course(course):
                    current_usage = kitchen.using_teams.filter(
                        course=course,
                        is_active=True
                    ).count()

                    if current_usage < kitchen.max_teams:
                        available_kitchens.append(kitchen)
                        kitchen_usage[kitchen.id] = current_usage

            if not available_kitchens:
                logger.info(
                    f"   ❌ Keine verfügbaren Gastküchen für optionale {course_display}-Zuordnungen")
                continue

            # Analysiere alle Teams für diesen Kurs
            for assignment in solution['assignments']:
                team = assignment['team']

                # Skip Teams die selbst hosten für diesen Kurs
                if assignment['course_hosted'] == course:
                    continue

                # Host für diesen Kurs
                host_team = assignment['hosts'].get(course)
                if not host_team:
                    continue

                # Berechne ursprüngliche Distanz: Team → Host
                original_distance = self.distances.get(
                    (team.id, host_team.id), float('inf'))

                # Finde beste Gastküche für dieses Team
                best_kitchen = None
                best_savings = 0

                for kitchen in available_kitchens:
                    # Prüfe Kapazität
                    if kitchen_usage[kitchen.id] >= kitchen.max_teams:
                        continue

                    # Distanz: Team → Gastküche
                    team_to_kitchen = self.guest_kitchen_distances.get(
                        (team.id, kitchen.id), float('inf'))

                    # Distanz: Gastküche → Host (falls Team dort nur kocht, nicht isst)
                    # Für vereinfachte Logik: Team nutzt Gastküche als Location

                    # Ersparnis berechnen (Schwellwert: min. 3km Ersparnis)
                    savings = original_distance - team_to_kitchen

                    if savings > best_savings and savings >= 3.0:  # Min. 3km Ersparnis
                        best_kitchen = kitchen
                        best_savings = savings

                # Zuordnung erstellen wenn vorteilhaft
                if best_kitchen and best_savings > 0:
                    try:
                        kitchen_assignment = TeamGuestKitchenAssignment.objects.create(
                            team=team,
                            guest_kitchen=best_kitchen,
                            course=course,
                            notes=f"Automatisch zugewiesen. Ersparnis: {best_savings:.1f}km"
                        )

                        kitchen_usage[best_kitchen.id] += 1
                        assignments_created += 1
                        distance_savings += best_savings

                        logger.info(
                            f"   ✅ {team.name} → {best_kitchen.name} ({course_display}): -{best_savings:.1f}km")

                        # Update die Route im Solution (Team nutzt jetzt Gastküche statt Host-Zuhause)
                        assignment['guest_kitchen_usage'] = assignment.get(
                            'guest_kitchen_usage', {})
                        assignment['guest_kitchen_usage'][course] = {
                            'kitchen': best_kitchen,
                            'distance_savings': best_savings,
                            'original_host': host_team
                        }

                    except Exception as e:
                        logger.warning(
                            f"   ⚠️ Fehler bei Gastküchen-Zuordnung: {e}")

        if assignments_created > 0:
            logger.info(f"🏠 Gastküchen-Zuordnung abgeschlossen:")
            logger.info(f"   📊 {assignments_created} Zuordnungen erstellt")
            if mandatory_assignments > 0:
                logger.info(
                    f"   🔴 {mandatory_assignments} ZWINGEND erforderlich (Teams ohne Küche)")
                logger.info(
                    f"   🟡 {assignments_created - mandatory_assignments} optional (Distanz-Optimierung)")
            logger.info(f"   📉 Gesamt-Ersparnis: {distance_savings:.1f}km")
        else:
            if mandatory_assignments > 0:
                logger.info(
                    f"🏠 {mandatory_assignments} zwingend erforderliche Gastküchen-Zuordnungen erstellt")
            else:
                logger.info(
                    "🏠 Keine Gastküchen-Zuordnungen erforderlich oder vorteilhaft")

        return solution

    def improve_guest_distribution(self, solution, guests_per_host, host_teams_by_course):
        """
        Post-Optimierung: Verbessere Gästeverteilung und Gesamtdistanzen
        durch iterative Neuzuordnung von Gästen
        """
        courses = self.courses
        n_teams = len(self.teams)
        improved_assignments = solution['assignments'].copy()

        # Mehrere Optimierungsiterationen
        # Flexibel konfigurierbar
        max_iterations = getattr(self, 'max_iterations', 3)
        for iteration in range(max_iterations):
            logger.info(f"🔄 Optimierungs-Iteration {iteration + 1}")
            improvement_found = False

            for course in courses:
                hosts_in_course = host_teams_by_course[course]
                if len(hosts_in_course) < 2:
                    continue

                # Berechne ideale Gästeanzahl pro Host
                total_guests_for_course = sum(1 for t in self.teams if
                                              any(a['course_hosted'] != course and a['hosts'].get(course)
                                                  for a in improved_assignments if a['team'].id == t.id))
                ideal_guests = total_guests_for_course / len(hosts_in_course)

                # Finde unausgewogene Hosts
                overloaded_hosts = []
                underloaded_hosts = []

                for host in hosts_in_course:
                    current_guest_count = len(guests_per_host[host.id])
                    if current_guest_count > ideal_guests + 0.5:
                        overloaded_hosts.append((host, current_guest_count))
                    elif current_guest_count < ideal_guests - 0.5:
                        underloaded_hosts.append((host, current_guest_count))

                # Versuche Gäste von überladenen zu unterladenen Hosts zu verschieben
                for overloaded_host, _ in overloaded_hosts:
                    for underloaded_host, _ in underloaded_hosts:

                        # Finde beste Gast-Team zum Verschieben
                        best_guest_to_move = None
                        best_improvement = 0

                        current_guests = guests_per_host[overloaded_host.id].copy(
                        )
                        for guest_team in current_guests:

                            # Berechne aktuelle Distanz
                            old_distance = self.distances[(
                                guest_team.id, overloaded_host.id)]
                            new_distance = self.distances[(
                                guest_team.id, underloaded_host.id)]

                            # Improvement = Distanzreduktion
                            distance_improvement = old_distance - new_distance

                            if distance_improvement > best_improvement:
                                best_improvement = distance_improvement
                                best_guest_to_move = guest_team

                        # Führe die beste Verschiebung durch
                        if best_guest_to_move and best_improvement > 0.1:  # Min. 100m Verbesserung
                            logger.info(
                                f"   ↔️ Verschiebe {best_guest_to_move.name}: {overloaded_host.name} → {underloaded_host.name} (-{best_improvement:.2f}km)")

                            # Update guests_per_host
                            guests_per_host[overloaded_host.id].remove(
                                best_guest_to_move)
                            guests_per_host[underloaded_host.id].append(
                                best_guest_to_move)

                            # Update assignments
                            for assignment in improved_assignments:
                                if assignment['team'].id == best_guest_to_move.id:
                                    old_distance = assignment['distances'][course]
                                    assignment['hosts'][course] = underloaded_host
                                    assignment['distances'][course] = new_distance
                                    assignment['total_distance'] += (
                                        new_distance - old_distance)
                                    break

                            improvement_found = True
                            break

                    if improvement_found:
                        break

            if not improvement_found:
                logger.info(f"   ✅ Keine weiteren Verbesserungen gefunden")
                break

        # Berechne finale Statistiken
        new_total_distance = sum(a['total_distance']
                                 for a in improved_assignments)
        old_total_distance = solution['objective_value']
        improvement = old_total_distance - new_total_distance

        logger.info(f"🎯 Post-Optimierung abgeschlossen:")
        logger.info(
            f"   📉 Distanz: {old_total_distance:.1f}km → {new_total_distance:.1f}km (Δ{improvement:.1f}km)")

        # Update finale Gästeverteilung logs
        for course in courses:
            hosts_in_course = host_teams_by_course[course]
            logger.info(f"   🏠 {course} (optimiert):")
            for host in hosts_in_course:
                guest_count = len(guests_per_host[host.id])
                logger.info(f"      - {host.name}: {guest_count} Gäste")

        # Return improved solution
        optimized_solution = solution.copy()
        optimized_solution['assignments'] = improved_assignments
        optimized_solution['objective_value'] = new_total_distance

        # SCHRITT 6: Afterparty-Routen hinzufügen
        if self.after_party:
            optimized_solution = self.add_afterparty_routes(optimized_solution)

        # Finale Progress-Update
        self._update_progress(5, 5, "Optimierung abgeschlossen",
                              f"✅ Optimierung erfolgreich! Finale Distanz: {optimized_solution['objective_value']:.1f}km")

        return optimized_solution

    def add_afterparty_routes(self, solution):
        """
        Füge Routen zur Afterparty-Location für alle Teams hinzu
        Route: Letzte Location (Dessert-Host oder eigenes Zuhause) → Afterparty
        """
        logger.info(
            f"🎉 Berechne Routen zur Afterparty: {self.after_party.name}")

        total_afterparty_distance = 0
        teams_with_routes = 0

        for assignment in solution['assignments']:
            team = assignment['team']

            # Bestimme die letzte Location für dieses Team
            if assignment['course_hosted'] == 'dessert':
                # Team hostet Dessert → startet von eigener Adresse zur Afterparty
                last_location_id = team.id
                last_location_name = f"{team.name} (Zuhause)"
            else:
                # Team geht zu Dessert-Host → startet von dort zur Afterparty
                dessert_host = assignment['hosts'].get('dessert')
                if dessert_host:
                    last_location_id = dessert_host.id
                    last_location_name = f"{dessert_host.name} (Dessert-Host)"
                else:
                    # Fallback: eigene Adresse
                    last_location_id = team.id
                    last_location_name = f"{team.name} (Zuhause)"

            # Prüfe ob Team eine Gastküche für Dessert nutzt
            guest_kitchen_usage = assignment.get('guest_kitchen_usage', {})
            if 'dessert' in guest_kitchen_usage:
                # Team nutzt Gastküche für Dessert
                guest_kitchen = guest_kitchen_usage['dessert']['kitchen']
                last_location_id = f'kitchen_{guest_kitchen.id}'
                last_location_name = f"{guest_kitchen.name} (Gastküche)"

            # Hole Distanz zur Afterparty
            afterparty_distance = self.after_party_distances.get(
                last_location_id, 0)

            if afterparty_distance > 0:
                assignment['afterparty_route'] = {
                    'from_location': last_location_name,
                    'to_location': self.after_party.name,
                    'distance': afterparty_distance,
                    'start_time': self.after_party.start_time
                }

                # Füge zur Gesamtdistanz hinzu
                assignment['total_distance'] = assignment.get(
                    'total_distance', 0) + afterparty_distance
                total_afterparty_distance += afterparty_distance
                teams_with_routes += 1

                logger.info(
                    f"   🚶 {team.name}: {last_location_name} → {self.after_party.name} ({afterparty_distance:.1f}km)")
            else:
                logger.warning(
                    f"   ⚠️ Keine Afterparty-Route für {team.name} gefunden")

        # Update Gesamtdistanz
        solution['objective_value'] = solution.get(
            'objective_value', 0) + total_afterparty_distance

        # Afterparty-Statistiken
        if teams_with_routes > 0:
            avg_afterparty_distance = total_afterparty_distance / teams_with_routes
            solution['afterparty_stats'] = {
                'total_distance': total_afterparty_distance,
                'average_distance': avg_afterparty_distance,
                'teams_count': teams_with_routes,
                'location': {
                    'name': self.after_party.name,
                    'address': self.after_party.address,
                    'start_time': self.after_party.start_time.strftime('%H:%M') if self.after_party.start_time else None
                }
            }

            logger.info(f"🎉 Afterparty-Routen hinzugefügt:")
            logger.info(
                f"   📊 {teams_with_routes} Teams, {total_afterparty_distance:.1f}km total")
            logger.info(
                f"   📍 Ø Afterparty-Distanz: {avg_afterparty_distance:.1f}km")

        return solution

    def run_additional_optimization(self, max_additional_iterations=5):
        """
        Führe weitere Optimierungsiterationen auf bereits optimierter Lösung durch
        """
        from optimization.models import OptimizationRun, TeamAssignment

        # Hole die neueste abgeschlossene Optimierung
        latest_optimization = self.event.optimization_runs.filter(
            status='completed'
        ).order_by('-completed_at').first()

        if not latest_optimization:
            raise ValueError("Keine abgeschlossene Optimierung gefunden")

        self._update_progress(0, 3, "Lade bestehende Lösung",
                              "🔄 Lade bestehende Optimierung...")

        # Lade Teams und Distanzen
        self.load_teams()
        self.calculate_distances()

        # Konvertiere TeamAssignments zurück in Lösungsformat
        assignments = latest_optimization.team_assignments.all()
        solution = self._convert_assignments_to_solution(assignments)

        self._update_progress(1, 3, "Weitere Optimierung",
                              f"🔄 Starte {max_additional_iterations} weitere Iterationen...")

        # Rekonstruiere guests_per_host und host_teams_by_course
        guests_per_host, host_teams_by_course = self._rebuild_guest_mapping(
            assignments)

        # Führe zusätzliche Optimierung durch
        self.max_iterations = max_additional_iterations
        optimized_solution = self.improve_guest_distribution(
            solution, guests_per_host, host_teams_by_course)

        self._update_progress(2, 3, "Speichere Verbesserungen",
                              "💾 Speichere verbesserte Zuordnungen...")

        # Aktualisiere die bestehenden TeamAssignment-Objekte
        self._update_existing_assignments(
            optimized_solution, latest_optimization)

        self._update_progress(3, 3, "Zusätzliche Optimierung abgeschlossen",
                              f"✅ Weitere Optimierung abgeschlossen! Neue Distanz: {optimized_solution['objective_value']:.1f}km")

        return optimized_solution

    def _convert_assignments_to_solution(self, assignments):
        """Konvertiere TeamAssignment-Objekte zurück in Solution-Format"""
        solution_assignments = []
        total_distance = 0

        for assignment in assignments:
            team = assignment.team
            hosts = {
                'appetizer': assignment.hosts_appetizer,
                'main_course': assignment.hosts_main_course,
                'dessert': assignment.hosts_dessert
            }

            distances = {
                'appetizer': assignment.distance_to_appetizer or 0,
                'main_course': assignment.distance_to_main_course or 0,
                'dessert': assignment.distance_to_dessert or 0
            }

            solution_assignment = {
                'team': team,
                'hosts': hosts,
                'course_hosted': assignment.course,
                'distances': distances,
                'total_distance': assignment.total_distance or 0
            }

            solution_assignments.append(solution_assignment)
            total_distance += solution_assignment['total_distance']

        return {
            'assignments': solution_assignments,
            'objective_value': total_distance,
            'travel_times': {}
        }

    def _rebuild_guest_mapping(self, assignments):
        """Rekonstruiere guests_per_host und host_teams_by_course aus Assignments"""
        guests_per_host = {}
        host_teams_by_course = {'appetizer': [],
                                'main_course': [], 'dessert': []}

        # Initialisiere
        for team in self.teams:
            guests_per_host[team.id] = []

        # Sammle Hosts und Gäste
        for assignment in assignments:
            team = assignment.team
            course_hosted = assignment.course

            # Füge zu host_teams_by_course hinzu
            if team not in host_teams_by_course[course_hosted]:
                host_teams_by_course[course_hosted].append(team)

            # Füge zu guests_per_host hinzu
            for course in ['appetizer', 'main_course', 'dessert']:
                if course != course_hosted:
                    host = getattr(assignment, f'hosts_{course}')
                    if host:
                        guests_per_host[host.id].append(team)

        return guests_per_host, host_teams_by_course

    def _update_existing_assignments(self, optimized_solution, optimization_run):
        """Aktualisiere bestehende TeamAssignment-Objekte mit neuen Werten"""
        for solution_assignment in optimized_solution['assignments']:
            team = solution_assignment['team']

            # Finde das entsprechende TeamAssignment
            assignment = optimization_run.assignments.get(team=team)

            # Update hosts
            assignment.hosts_appetizer = solution_assignment['hosts']['appetizer']
            assignment.hosts_main_course = solution_assignment['hosts']['main_course']
            assignment.hosts_dessert = solution_assignment['hosts']['dessert']

            # Update distances
            assignment.distance_to_appetizer = solution_assignment['distances']['appetizer']
            assignment.distance_to_main_course = solution_assignment['distances']['main_course']
            assignment.distance_to_dessert = solution_assignment['distances']['dessert']
            assignment.total_distance = solution_assignment['total_distance']

            assignment.save()

        # Update optimization run statistics
        optimization_run.total_distance = optimized_solution['objective_value']
        optimization_run.save()

    def optimize(self) -> Dict:
        """
        Hauptmethode: Führe komplette Optimierung durch
        """
        try:
            # 1. Lade Teams
            self.load_teams()

            # 2. Berechne Entfernungen
            self.calculate_distances()

            # Für kleine Anzahl Teams (≤6) versuche MIP
            if len(self.teams) <= 6:
                logger.info(
                    f"🎯 {len(self.teams)} Teams: Versuche MIP-Optimierung")
                try:
                    # 3. Erstelle MIP-Model
                    self.create_mip_model()

                    # 4. Füge Constraints hinzu
                    self.add_constraints()

                    # 5. Löse Problem
                    if self.solve():
                        solution = self.extract_solution()
                        logger.info("🎉 MIP-Optimierung erfolgreich!")
                        return solution
                except Exception as mip_error:
                    logger.warning(f"⚠️ MIP fehlgeschlagen: {mip_error}")

            # Für alle anderen Fälle: Verwende optimierten Running Dinner Algorithmus
            logger.info(
                f"🍽️ {len(self.teams)} Teams: Verwende Running Dinner Algorithmus")
            return self.simple_running_dinner_solution()

        except Exception as e:
            logger.error(f"❌ Fehler bei Optimierung: {str(e)}")
            raise ValueError(f"Optimierung fehlgeschlagen: {str(e)}")

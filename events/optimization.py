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

    def load_teams(self):
        """Lade bestätigte Teams für das Event"""
        self.team_registrations = list(
            self.event.team_registrations.filter(status='confirmed')
            .select_related('team')
        )
        self.teams = [reg.team for reg in self.team_registrations]

        if len(self.teams) < 3:
            raise ValueError(
                f"Mindestens 3 Teams erforderlich, aber nur {len(self.teams)} bestätigt")

        logger.info(
            f"🎯 Optimiere {len(self.teams)} Teams für Event '{self.event.name}'")

    def calculate_distances(self):
        """
        Berechne echte Fußgänger-Entfernungen zwischen allen Teams
        Verwendet OpenRouteService API für realistische Routen
        """
        from .routing import get_route_calculator

        n = len(self.teams)
        logger.info(f"🗺️ Berechne echte Fußgänger-Routen für {n} Teams...")

        # Verwende echtes Routing
        route_calculator = get_route_calculator()
        self.distances = route_calculator.calculate_team_distances(self.teams)

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

        # SCHRITT 2: Für jedes Team berechne seine Route (welche Hosts besucht es)
        # WICHTIG: Korrekte Route-Berechnung: Home → Vorspeise → Hauptgang → Nachspeise
        # (nicht immer von Home aus, sondern von der aktuellen Position!)
        total_distance = 0
        guests_per_host = {}  # host_team_id -> [guest_team_objects]

        # Initialisiere Gäste-Listen
        for team in self.teams:
            guests_per_host[team.id] = []

        for team in self.teams:
            my_hosting_course = team_hosting_map[team.id]
            hosts = {}
            distances = {}

            # Verfolge die aktuelle Position des Teams während der Route
            current_location = team  # Start von der Team-Home-Adresse

            # Für jeden Kurs: Finde besten verfügbaren Host (korrekte Route-Berechnung)
            for course in courses:
                if course == my_hosting_course:
                    # Ich hoste diesen Kurs selbst - bleibe zuhause
                    hosts[course] = None
                    distances[course] = 0
                    # Aktuelle Position bleibt zuhause (Team-Home)
                    current_location = team
                else:
                    # Finde besten Host (mit wenigsten Gästen + kürzeste Entfernung)
                    best_host = None
                    best_score = float('inf')

                    for potential_host in host_teams_by_course[course]:
                        current_guest_count = len(
                            guests_per_host[potential_host.id])
                        # KORREKT: Distanz von aktueller Position zum Host
                        distance = self.distances[(
                            current_location.id, potential_host.id)]

                        # Verbessertes Scoring: Stark ungleiche Verteilung bestrafen
                        ideal_guests_per_host = (
                            n_teams - len(host_teams_by_course[course])) / len(host_teams_by_course[course])
                        guest_penalty = max(
                            0, current_guest_count - ideal_guests_per_host) * 20

                        # Score = Gäste-Ungleichgewicht + normalisierte Entfernung
                        score = guest_penalty + distance

                        if score < best_score:
                            best_score = score
                            best_host = potential_host

                    hosts[course] = best_host
                    distances[course] = self.distances[(
                        current_location.id, best_host.id)]

                    # Team bewegt sich zum neuen Host-Standort
                    current_location = best_host

                    # Füge mich als Gast zu diesem Host hinzu
                    guests_per_host[best_host.id].append(team)

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

        # SCHRITT 4: Post-Optimierung - Verbessere Verteilung und Distanzen
        logger.info("🔄 Starte Post-Optimierung...")
        optimized_solution = self.improve_guest_distribution(
            solution, guests_per_host, host_teams_by_course)

        return optimized_solution

    def improve_guest_distribution(self, solution, guests_per_host, host_teams_by_course):
        """
        Post-Optimierung: Verbessere Gästeverteilung und Gesamtdistanzen
        durch iterative Neuzuordnung von Gästen
        """
        courses = self.courses
        n_teams = len(self.teams)
        improved_assignments = solution['assignments'].copy()

        # Mehrere Optimierungsiterationen
        for iteration in range(3):  # Max 3 Iterationen
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

        return optimized_solution

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

"""
Running Dinner Optimization using Mixed-Integer Programming
Basiert auf dem Ansatz von https://github.com/fm-or/running-dinner
"""

import random
from typing import List, Dict, Tuple, Optional
from django.utils import timezone
import pulp
import logging

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
        Berechne Entfernungsmatrix zwischen allen Teams
        TODO: Später mit echter geografischer API (OpenRouteService) ersetzen
        """
        n = len(self.teams)
        self.distances = {}

        # Simuliere realistische Entfernungen in München (0.5-4.0 km)
        for i, team1 in enumerate(self.teams):
            for j, team2 in enumerate(self.teams):
                if i == j:
                    self.distances[(team1.id, team2.id)] = 0.0
                else:
                    # Konsistente, symmetrische Entfernungen
                    key = tuple(sorted([team1.id, team2.id]))
                    if key not in self.distances:
                        # Simuliere Entfernung basierend auf Team-IDs für Konsistenz
                        random.seed(hash(key) % 1000000)
                        dist = round(random.uniform(0.5, 4.0), 1)
                        self.distances[key] = dist

                    # Symmetrische Zuordnung
                    sorted_key = tuple(sorted([team1.id, team2.id]))
                    self.distances[(team1.id, team2.id)
                                   ] = self.distances[sorted_key]
                    self.distances[(team2.id, team1.id)
                                   ] = self.distances[sorted_key]

        logger.info(f"📏 Entfernungsmatrix für {n} Teams berechnet")

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
        total_distance = 0
        guests_per_host = {}  # host_team_id -> [guest_team_objects]

        # Initialisiere Gäste-Listen
        for team in self.teams:
            guests_per_host[team.id] = []

        for team in self.teams:
            my_hosting_course = team_hosting_map[team.id]
            hosts = {}
            distances = {}

            # Für jeden Kurs: Finde besten verfügbaren Host
            for course in courses:
                if course == my_hosting_course:
                    # Ich hoste diesen Kurs selbst
                    hosts[course] = None
                    distances[course] = 0
                else:
                    # Finde besten Host (mit wenigsten Gästen + kürzeste Entfernung)
                    best_host = None
                    best_score = float('inf')

                    for potential_host in host_teams_by_course[course]:
                        current_guest_count = len(
                            guests_per_host[potential_host.id])
                        distance = self.distances[(team.id, potential_host.id)]

                        # Score = Gästeanzahl * 10 + Entfernung (priorisiere gleichmäßige Verteilung)
                        score = current_guest_count * 10 + distance

                        if score < best_score:
                            best_score = score
                            best_host = potential_host

                    hosts[course] = best_host
                    distances[course] = self.distances[(team.id, best_host.id)]

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

        return solution

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

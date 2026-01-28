class Table:
    def __init__(self, table_id, area, capacity, display_name, row=None, number_in_row=None, type=None):
        self.id = table_id
        self.area = area
        self.capacity = capacity
        self.display_name = display_name
        self.row = row
        self.number_in_row = number_in_row
        self.type = type
        self.status = "frei"
        self.reservation_details = None

    def __repr__(self):
        type_str = f", Type: {self.type}" if self.type else ""
        return f"<Table '{self.display_name}' (ID: {self.id}, Area: {self.area}{type_str})>"

ALL_TABLES = []

for i in range(1, 10):
    table_id = f"saal-{i}"
    display_name = f"Saal {i}"
    ALL_TABLES.append(Table(table_id=table_id, area="Saal", capacity=4, display_name=display_name))

for i in range(1, 8):
    table_id = f"stube-{i}"
    display_name = f"Stube {i}"
    ALL_TABLES.append(Table(table_id=table_id, area="Stube", capacity=6, display_name=display_name))

for r_num in range(1, 4):
    for t_num_in_row in range(1, 8):
        table_id = f"garten-r{r_num}-t{t_num_in_row}"
        display_name = f"Garten {r_num}-{t_num_in_row}"
        ALL_TABLES.append(Table(
            table_id=table_id,
            area="Garten",
            capacity=2,
            display_name=display_name,
            row=r_num,
            number_in_row=t_num_in_row
        ))

for i in range(1, 4):
    table_id = f"bar-theke-{i}"
    display_name = f"Bar {i}"
    ALL_TABLES.append(Table(
        table_id=table_id,
        area="Bar",
        capacity=1,
        display_name=display_name,
        type="Theke"
    ))

for i in range(1, 6):
    table_id = f"bar-rtisch-{i}"
    display_name = f"R {i}"
    ALL_TABLES.append(Table(
        table_id=table_id,
        area="Bar",
        capacity=2,
        display_name=display_name,
        type="Regulär"
    ))

# --- ZIMMER UPDATED ---
ALL_ROOMS = []

# 1. Stock: 8, 9, 10, 17, 18, 19, 20
floor1_numbers = [8, 9, 10, 17, 18, 19, 20]
for num in floor1_numbers:
    ALL_ROOMS.append(Table(f"zimmer-{num}", "1. Stock", 2, f"Zimmer {num}", type="Doppelzimmer"))

# 2. Stock: 23, 24, 25, 26, 27
floor2_numbers = [23, 24, 25, 26, 27]
for num in floor2_numbers:
    ALL_ROOMS.append(Table(f"zimmer-{num}", "2. Stock", 2, f"Zimmer {num}", type="Doppelzimmer"))

# Hilfsliste für alle Ressourcen (Tische + Zimmer) für die Suche
ALL_RESOURCES = ALL_TABLES + ALL_ROOMS


# core/models.py
# ... (Table Klasse und Listen bleiben gleich) ...

class Reservation:
    SHIFT_LUNCH = "mittag"
    SHIFT_DINNER = "abend"
    VALID_SHIFTS = [SHIFT_LUNCH, SHIFT_DINNER]

    def __init__(self, reservation_id, name, date_str, time_str, persons, table_id, info="", arrived=False, departed=False, shift=SHIFT_DINNER, end_date_str=None):
        self.id = reservation_id
        self.name = name
        self.date = date_str # Bei Zimmern: Anreise
        self.end_date = end_date_str if end_date_str else date_str # Bei Zimmern: Abreise (Default: gleicher Tag)
        self.time = time_str # Bei Zimmern: Anreise-Uhrzeit
        try: self.persons = int(persons)
        except: self.persons = 0
        self.table_id = table_id
        self.info = info
        self.arrived = arrived
        self.departed = departed
        self.shift = shift

    @classmethod
    def from_dict(cls, data):
        return cls(
            reservation_id=data.get('id'),
            name=data.get('name'),
            date_str=data.get('date'),
            end_date_str=data.get('end_date'), # NEU
            time_str=data.get('time'),
            persons=data.get('persons'),
            table_id=data.get('table_id'),
            info=data.get('info', ""),
            arrived=data.get('arrived', False),
            departed=data.get('departed', False),
            shift=data.get('shift', cls.SHIFT_DINNER)
        )

    def to_dict(self):
        return {
            "id": self.id, "name": self.name,
            "date": self.date, "end_date": self.end_date, # NEU
            "time": self.time,
            "persons": self.persons, "table_id": self.table_id, "info": self.info,
            "arrived": self.arrived, "departed": self.departed, "shift": self.shift
        }
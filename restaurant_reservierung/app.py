from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import datetime, os
import calendar
from datetime import timedelta
from core import manager
from core.models import ALL_TABLES, ALL_ROOMS, ALL_RESOURCES, Reservation, Reservation as ResModel
from core.translations import TRANSLATIONS
import logging

logging.basicConfig(level=logging.DEBUG, # Setze das gewünschte globale Level
                    format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s')

app = Flask(__name__)
app.secret_key = os.urandom(24)

# HIER NEU EINFÜGEN:
USERS = {
    "admin": "admin123",
}

if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
    with app.app_context():
        # Rufe hier die manager-Funktionen auf, die beim Start ausgeführt werden sollen
        # z.B. auch manager.cleanup_old_backups(), wenn du es nicht nach jedem Speichern machen willst
        pass # Dein Initialisierungscode

with app.app_context():
    print("Führe initiale Bereinigung alter Reservierungen durch...")
    manager.cleanup_old_reservations()

def get_table_display_name_by_id(table_id):
    for t in ALL_RESOURCES:
        if t.id == table_id:
            return t.display_name
    return table_id


def format_date_european(date_str_yyyy_mm_dd):
    if not date_str_yyyy_mm_dd:
        return ""
    try:
        dt_obj = datetime.datetime.strptime(date_str_yyyy_mm_dd, "%Y-%m-%d")
        return dt_obj.strftime("%d.%m.%Y")
    except ValueError:
        return date_str_yyyy_mm_dd


@app.context_processor
def inject_global_vars():
    return {
        'current_year': datetime.datetime.now().year,
        'active_nav_tab': request.endpoint,
        'SHIFT_LUNCH': Reservation.SHIFT_LUNCH,
        'SHIFT_DINNER': Reservation.SHIFT_DINNER,
        'VALID_SHIFTS': Reservation.VALID_SHIFTS
    }


@app.context_processor
def inject_translations():
    # Standardsprache ist Deutsch ('de')
    current_lang = session.get('language', 'de')

    # Hole das Wörterbuch für die aktuelle Sprache
    texts = TRANSLATIONS.get(current_lang, TRANSLATIONS['de'])

    return dict(t=texts, current_lang=current_lang)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Prüfen ob Benutzer existiert und Passwort stimmt
        if username in USERS and USERS[username] == password:
            session['logged_in'] = True
            session['username'] = username
            app.logger.info(f"Benutzer '{username}' hat sich angemeldet.")
            return redirect(url_for('index'))
        else:
            error = 'Ungültige Zugangsdaten. Bitte erneut versuchen.'
            app.logger.warning(f"Fehlgeschlagener Login-Versuch für User: {username}")

    return render_template('login.html', error=error)

@app.before_request
def require_login():
    # Liste der Endpunkte, die man OHNE Login sehen darf
    allowed_routes = ['login', 'static']

    # Wenn der Benutzer nicht eingeloggt ist UND die Seite nicht erlaubt ist -> Login
    if 'logged_in' not in session and request.endpoint not in allowed_routes:
        # Ein kleiner Check, damit statische Dateien (CSS/JS) nicht blockiert werden
        if request.endpoint and 'static' in request.endpoint:
            return

        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear() # Löscht alle Daten aus der Sitzung
    return redirect(url_for('login'))

@app.route('/set_language/<lang_code>')
def set_language(lang_code):
    if lang_code in ['de', 'it', 'en']:
        session['language'] = lang_code
    return redirect(request.referrer or url_for('index'))
@app.route('/')
def index():
    current_date_obj = datetime.date.today()
    default_date_str = current_date_obj.strftime("%Y-%m-%d")

    selected_date_str = request.args.get('date', default_date_str)

    try:
        datetime.datetime.strptime(selected_date_str, "%Y-%m-%d")
    except ValueError:
        selected_date_str = default_date_str

    selected_shift = request.args.get('shift', Reservation.SHIFT_DINNER)
    if selected_shift not in Reservation.VALID_SHIFTS:
        selected_shift = Reservation.SHIFT_DINNER

    all_reservations_objects = manager.load_reservations()

    reservations_for_selected_date_and_shift = []
    for res_obj in all_reservations_objects:
        if res_obj.date == selected_date_str and res_obj.shift == selected_shift:
            reservations_for_selected_date_and_shift.append(res_obj)

    display_tables_data = []
    for table_model in ALL_TABLES:
        table_data = {
            'id': table_model.id,
            'area': table_model.area,
            'capacity': table_model.capacity,
            'display_name': table_model.display_name,
            'row': table_model.row,
            'number_in_row': table_model.number_in_row,
            'type': table_model.type,  # <<<< HIER DAS 'type'-ATTRIBUT HINZUFÜGEN
            'status': "frei",
            'reservations_on_table': []
        }

        current_table_reservations_details_for_display = []  # Für die Anzeige aller Reservierungen dieses Tisches
        is_table_actively_occupied = False  # Ist der Tisch *momentan* durch einen anwesenden Gast belegt?

        for res_obj in reservations_for_selected_date_and_shift:  # Diese sollten volle Reservation-Objekte sein
            if res_obj.table_id == table_model.id:
                # Details für die Anzeige im Tischkasten sammeln (alle Reservierungen des Tages)
                current_table_reservations_details_for_display.append({
                    'id': res_obj.id,
                    'name': res_obj.name,
                    'time': res_obj.time,
                    'persons': res_obj.persons,
                    'info': res_obj.info,
                    'arrived': res_obj.arrived,
                    'departed': getattr(res_obj, 'departed', False)  # Sicherstellen, dass departed vorhanden ist
                })

                # Prüfen, ob der Tisch DURCH DIESE Reservierung AKTIV BELEGT ist
                if res_obj.arrived and not getattr(res_obj, 'departed', False):
                    is_table_actively_occupied = True

        # Setze den Gesamtstatus des Tisches
        if is_table_actively_occupied:
            table_data['status'] = 'belegt'
        # Sonst bleibt er 'frei' (Standardwert)

        # Füge die gesammelten Reservierungsdetails (für die Anzeige) zum Tisch hinzu, sortiert nach Zeit
        if current_table_reservations_details_for_display:
            table_data['reservations_on_table'] = sorted(
                current_table_reservations_details_for_display,
                key=lambda r: datetime.datetime.strptime(r['time'], "%H:%M").time() if r.get(
                    'time') else datetime.time.min
            )
            # Die Anzeige, ob der Tisch generell Reservierungen hat, ist in 'reservations_on_table'.
            # Der 'status' (frei/belegt) spiegelt die *aktuelle* Belegung wider.

        display_tables_data.append(table_data)

    return render_template(
        'index.html',
        tables=display_tables_data,
        selected_date=selected_date_str,
        selected_shift=selected_shift,
        valid_shifts=Reservation.VALID_SHIFTS
    )


def generate_time_slots(start_hour, start_minute, end_hour, end_minute, interval_minutes):
    slots = []
    current_time = datetime.time(start_hour, start_minute)
    end_time_obj = datetime.time(end_hour, end_minute)
    base_date = datetime.date(2000, 1, 1)
    current_dt = datetime.datetime.combine(base_date, current_time)
    end_dt = datetime.datetime.combine(base_date, end_time_obj)

    if end_dt < current_dt:
        end_dt += datetime.timedelta(days=1)

    while current_dt <= end_dt:
        slots.append(current_dt.strftime("%H:%M"))
        current_dt += datetime.timedelta(minutes=interval_minutes)
    return slots


@app.route('/reservieren', methods=['GET'])
def reservation_form_page():
    table_id = request.args.get('table_id')
    # Falls kein Tischname da ist, ID nutzen
    table_name = request.args.get('table_name', get_table_display_name_by_id(table_id) if table_id else "Gewünschter Tisch")

    selected_date_from_url = request.args.get('date')
    final_selected_date = datetime.date.today().strftime("%Y-%m-%d")
    if selected_date_from_url:
        try:
            datetime.datetime.strptime(selected_date_from_url, "%Y-%m-%d")
            final_selected_date = selected_date_from_url
        except ValueError:
            pass

    current_shift_from_url = request.args.get('shift', Reservation.SHIFT_DINNER)
    if current_shift_from_url not in Reservation.VALID_SHIFTS:
        current_shift_from_url = Reservation.SHIFT_DINNER

    possible_times_for_current_shift = []
    if current_shift_from_url == Reservation.SHIFT_LUNCH:
        possible_times_for_current_shift = generate_time_slots(11, 0, 14, 0, 15)
    elif current_shift_from_url == Reservation.SHIFT_DINNER:
        possible_times_for_current_shift = generate_time_slots(17, 0, 22, 0, 15)

    available_times = []
    if table_id:
        for time_slot in possible_times_for_current_shift:
            # HIER WAR DER FEHLER: Wir übergeben die Argumente jetzt direkt passend zur neuen manager.py
            if manager.is_table_available_for_specific_reservation_time(
                    table_id,                # War table_id_to_check
                    final_selected_date,     # War date_str_to_check
                    time_slot,               # War time_str_to_check
                    current_shift_from_url   # War shift_to_check
            ):
                available_times.append(time_slot)
    else:
        available_times = possible_times_for_current_shift

    return render_template(
        'reservation_form.html',
        form_mode='new',
        table_id=table_id,
        table_name=table_name,
        selected_date=final_selected_date,
        available_shifts=Reservation.VALID_SHIFTS,
        current_shift=current_shift_from_url,
        available_times=available_times,
        reservation_data=None
    )


@app.route('/reservierung_bearbeiten/<string:reservation_id>', methods=['GET'])
def edit_reservation_page(reservation_id):
    reservation_object = manager.get_reservation_by_id(reservation_id)

    if reservation_object is None:
        return "Reservierung nicht gefunden", 404

    table_name_for_form = get_table_display_name_by_id(reservation_object.table_id)

    possible_times_for_current_shift = []
    if reservation_object.shift == Reservation.SHIFT_LUNCH:
        possible_times_for_current_shift = generate_time_slots(11, 0, 14, 0, 15)
    elif reservation_object.shift == Reservation.SHIFT_DINNER:
        possible_times_for_current_shift = generate_time_slots(17, 0, 22, 0, 15)

    available_times = []
    for time_slot in possible_times_for_current_shift:
        # HIER EBENFALLS ANPASSEN:
        if manager.is_table_available_for_specific_reservation_time(
                reservation_object.table_id,
                reservation_object.date,
                time_slot,
                reservation_object.shift,
                reservation_id_to_ignore=reservation_object.id
        ):
            available_times.append(time_slot)

    if reservation_object.time not in available_times:
        available_times.append(reservation_object.time)
        try:
            available_times.sort(key=lambda t_str: datetime.datetime.strptime(t_str, "%H:%M").time())
        except ValueError:
            available_times.sort()

    return render_template(
        'reservation_form.html',
        form_mode='edit',
        reservation_data=reservation_object.to_dict(),
        table_id=reservation_object.table_id,
        table_name=table_name_for_form,
        selected_date=reservation_object.date,
        available_shifts=Reservation.VALID_SHIFTS,
        current_shift=reservation_object.shift,
        available_times=available_times,
        current_reservation_id=reservation_object.id
    )


@app.route('/reservierungen')
def reservations_list_page():
    # ... (Filter Logik wie bisher) ...
    filter_date_param = request.args.get('filter_date')
    filter_shift_param = request.args.get('shift', Reservation.SHIFT_DINNER)

    # ... (Datum Logik wie bisher) ...
    current_date_obj = datetime.date.today()
    today_str = current_date_obj.strftime("%Y-%m-%d")
    min_filter_date_str = (current_date_obj - timedelta(days=manager.MAX_RESERVATION_AGE_DAYS)).strftime("%Y-%m-%d")

    all_raw_reservations = manager.load_reservations()
    reservations_processed = []

    for res_obj in all_raw_reservations:
        res_dict = res_obj.to_dict()
        res_dict['table_display_name'] = get_table_display_name_by_id(res_obj.table_id)
        res_dict['display_date'] = format_date_european(res_obj.date)

        # NEU: Abreisedatum formatieren
        res_dict['display_end_date'] = format_date_european(res_obj.end_date)

        # NEU: Versuchen, die Checkout-Zeit aus der Info zu holen (Format: "| Abreise: HH:MM")
        res_dict['checkout_time'] = "10:00"  # Standard
        if "Abreise:" in res_obj.info:
            try:
                # Simple string split logic
                parts = res_obj.info.split("Abreise:")
                if len(parts) > 1:
                    time_part = parts[1].strip().split(" ")[0]  # Nimmt die Zeit
                    res_dict['checkout_time'] = time_part
                    # Info bereinigen für die Anzeige (optional)
                    # res_dict['info'] = parts[0].replace("|", "").strip()
            except:
                pass

        reservations_processed.append(res_dict)

    current_page_reservations = []
    active_picker_date = today_str
    page_title = "Reservierungen"

    # ... (Filter Logik Datum/Shift wie bisher) ...
    if filter_date_param is None:
        current_page_reservations = [r for r in reservations_processed if
                                     r.get('date') == today_str and r.get('shift') == filter_shift_param]
        page_title = f"Reservierungen für heute ({filter_shift_param})"
    elif filter_date_param == "":
        # Bei "Alle anzeigen" wollen wir bei Zimmern vielleicht alle zukünftigen sehen
        current_page_reservations = [r for r in reservations_processed if r.get('date') >= today_str]
        # Falls Shift gefiltert werden soll, hier einkommentieren. Bei Zimmern ist Shift meist egal.
        # Aber um konsistent zu Tischen zu bleiben, filtern wir Shift nur bei Tischen (machen wir unten beim Split)
        page_title = "Alle zukünftigen Reservierungen"
        active_picker_date = ""
    else:
        current_page_reservations = [r for r in reservations_processed if
                                     r.get('date') == filter_date_param and r.get('shift') == filter_shift_param]
        page_title = f"Reservierungen am {format_date_european(filter_date_param)}"
        active_picker_date = filter_date_param

    # ... (Sortier Logik wie bisher) ...
    sort_by_param = request.args.get('sort_by', 'table_display_name')
    sort_order_param = request.args.get('order', 'asc')
    reverse_order = (sort_order_param == 'desc')

    current_page_reservations.sort(key=lambda r: str(r.get(sort_by_param, '')), reverse=reverse_order)

    next_sort_order_dict = {k: ('desc' if sort_by_param == k and sort_order_param == 'asc' else 'asc') for k in
                            ['name', 'table_display_name', 'date', 'time', 'persons']}

    # SPLIT: Tische vs Zimmer
    # WICHTIG: Tische filtern wir streng nach Schicht. Zimmer zeigen wir unabhängig von der Schicht an, wenn Datum passt (oder wir lassen die Filterung oben)

    reservations_rooms = [r for r in current_page_reservations if 'zimmer' in str(r.get('table_id', '')).lower()]
    reservations_tables = [r for r in current_page_reservations if 'zimmer' not in str(r.get('table_id', '')).lower()]

    return render_template(
        'reservations_list.html',
        reservations_tables=reservations_tables,
        reservations_rooms=reservations_rooms,
        active_filter_date=active_picker_date,
        page_title=page_title,
        current_sort_by=sort_by_param,
        current_sort_order=sort_order_param,
        next_sort_order=next_sort_order_dict,
        min_filter_date=min_filter_date_str,
        available_shifts=Reservation.VALID_SHIFTS,
        current_filter_shift=filter_shift_param
    )


@app.route('/zimmer-buchen')
def room_booking_calendar():
    today = datetime.date.today()
    try:
        year = int(request.args.get('year', today.year))
        month = int(request.args.get('month', today.month))
    except ValueError:
        year = today.year
        month = today.month

    # Nächster Monat für die Anzeige (Rechte Seite)
    next_month_val = month + 1
    next_year_val = year
    if next_month_val > 12:
        next_month_val = 1
        next_year_val = year + 1

    cal = calendar.Calendar(firstweekday=0)
    month1_days = cal.monthdatescalendar(year, month)
    month2_days = cal.monthdatescalendar(next_year_val, next_month_val)

    month_names = {1: 'Januar', 2: 'Februar', 3: 'März', 4: 'April', 5: 'Mai', 6: 'Juni', 7: 'Juli', 8: 'August',
                   9: 'September', 10: 'Oktober', 11: 'November', 12: 'Dezember'}

    # LOGIK FIX FÜR NAVIGATION (Schieben um 1 Monat)
    # Vorheriger Monat
    prev_m = month - 1
    prev_y = year
    if prev_m < 1:
        prev_m = 12
        prev_y = year - 1

    # Nächster Monat (Startmonat + 1)
    next_m = month + 1
    next_y = year
    if next_m > 12:
        next_m = 1
        next_y = year + 1

    return render_template(
        'room_booking.html',
        month1_data=month1_days,
        month2_data=month2_days,
        m1_name=month_names[month],
        m2_name=month_names[next_month_val],
        year1=year, month1=month,
        year2=next_year_val, month2=next_month_val,
        # Hier die korrigierten URLs:
        prev_month_url=url_for('room_booking_calendar', year=prev_y, month=prev_m),
        next_month_url=url_for('room_booking_calendar', year=next_y, month=next_m)
    )


@app.route('/api/neue_reservierung', methods=['POST'])
def api_create_reservation():
    try:
        data = request.get_json()
        table_id = data.get('table_id', '')
        is_room = "zimmer" in table_id.lower()

        if is_room:
            # --- ZIMMER LOGIK ---
            # Hier nutzen wir die neue Zimmer-Prüfung
            if not manager.is_room_available(table_id, data['date'], data['end_date']):
                return jsonify({"success": False, "message": "Zimmer im gewählten Zeitraum bereits belegt."}), 409

            manager.create_reservation(
                name=data['name'],
                date=data['date'],
                time=data['time'],
                persons=int(data['persons']),
                table_id=table_id,
                info=data.get('info', "") + f" | Abreise: {data.get('checkout_time', 'Standard')}",
                shift="abend",
                end_date=data['end_date']
            )
            return jsonify(
                {"success": True, "message": "Zimmer gebucht!", "redirect_url": url_for('reservations_list_page')})

        else:
            # --- TISCH LOGIK ---
            # HIER WAR DER FEHLER: Wir rufen die Funktion jetzt ohne die alten Schlüsselwörter auf
            if not manager.is_table_available_for_specific_reservation_time(
                    table_id,  # früher table_id_to_check
                    data['date'],  # früher date_str_to_check
                    data['time'],  # früher time_str_to_check
                    data['shift']  # früher shift_to_check
            ):
                return jsonify({"success": False, "message": "Tisch zur gewählten Zeit bereits belegt."}), 409

            manager.create_reservation(
                name=data['name'],
                date=data['date'],
                time=data['time'],
                persons=int(data['persons']),
                table_id=table_id,
                info=data.get('info', ""),
                shift=data['shift']
                # end_date ist hier optional und wird im Manager automatisch gesetzt
            )

            return jsonify({"success": True, "message": "Tisch reserviert!",
                            "redirect_url": url_for('index', date=data['date'], shift=data['shift'])})

    except Exception as e:
        app.logger.error(f"Fehler beim Erstellen: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Serverfehler: {str(e)}"}), 50

@app.route('/api/freie_zimmer_suchen', methods=['POST'])
def api_search_rooms():
    data = request.get_json()
    start = data.get('start_date')
    end = data.get('end_date')

    free_rooms = []
    # Alle Zimmer durchgehen
    for room in ALL_ROOMS:  # Import sicherstellen!
        if manager.is_room_available(room.id, start, end):
            free_rooms.append({
                "id": room.id,
                "display_name": room.display_name,
                "area": room.area,
                "capacity": room.capacity
            })

    return jsonify({"success": True, "rooms": free_rooms})


@app.route('/api/reservierung_bearbeiten/<string:reservation_id>', methods=['POST'])
def api_update_reservation(reservation_id):
    try:
        data = request.get_json()
        original_res = manager.get_reservation_by_id(reservation_id)
        if not original_res:
            return jsonify({"success": False, "message": "Reservierung nicht gefunden."}), 404

        table_id = data.get('table_id', original_res.table_id)
        is_room = "zimmer" in table_id.lower()

        if is_room:
            # ZIMMER UPDATE
            start_date = data.get('date', original_res.date)
            # end_date aus dem Request holen oder vom Original
            end_date = data.get('end_date', original_res.end_date)

            # Hinweis: Eine echte Verfügbarkeitsprüfung beim Update ist komplex (man muss sich selbst ignorieren).
            # Wir speichern hier direkt das Update.

            manager.update_reservation(
                reservation_id_to_update=reservation_id,
                name=data.get('name'),
                date_str=start_date,
                time_str=data.get('time'),
                persons=int(data['persons']),
                table_id=table_id,
                info=data.get('info'),
                shift="abend"
            )

            # Manuelles Update für end_date, da update_reservation das ggf. noch nicht unterstützt hat in alten Versionen
            # (Falls du update_reservation im Manager noch nicht angepasst hast)
            res = manager.get_reservation_by_id(reservation_id)
            res.end_date = end_date
            # Erzwinge Speichern
            manager.save_reservations(manager.load_reservations())

        else:
            # TISCH UPDATE
            target_date = data.get('date', original_res.date)
            target_time = data.get('time', original_res.time)
            target_shift = data.get('shift', original_res.shift)

            # Nur prüfen, wenn sich relevante Daten geändert haben
            if (
                    target_date != original_res.date or target_time != original_res.time or target_shift != original_res.shift):
                # AUCH HIER KORRIGIERT: Argumente ohne Keywords
                if not manager.is_table_available_for_specific_reservation_time(
                        table_id, target_date, target_time, target_shift, reservation_id_to_ignore=reservation_id):
                    return jsonify({"success": False, "message": "Tisch ist zur neuen Zeit belegt."}), 409

            manager.update_reservation(
                reservation_id_to_update=reservation_id,
                name=data.get('name'),
                date_str=target_date,
                time_str=target_time,
                persons=int(data['persons']),
                table_id=table_id,
                info=data.get('info'),
                shift=target_shift
            )

        return jsonify({"success": True, "message": "Aktualisiert.", "redirect_url": url_for('reservations_list_page')})

    except Exception as e:
        app.logger.error(f"Fehler beim Update: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Serverfehler: {str(e)}"}), 500

@app.route('/api/reservierung_loeschen/<string:reservation_id>', methods=['DELETE'])
def api_delete_reservation(reservation_id):
    success = manager.delete_reservation(reservation_id)
    if success:
        return jsonify({"success": True, "message": "Reservierung erfolgreich gelöscht."})
    else:
        return jsonify({"success": False, "message": "Reservierung nicht gefunden oder Fehler beim Löschen."}), 404


@app.route('/api/available_tables_for_move/<string:reservation_id>', methods=['GET'])
def api_get_available_tables_for_move(reservation_id):
    original_reservation = manager.get_reservation_by_id(reservation_id)
    if not original_reservation:
        return jsonify({"success": False, "message": "Ursprüngliche Reservierung nicht gefunden."}), 404

    try:
        available_tables_objects = manager.get_available_tables_for_moving(original_reservation)
        available_tables_data = []
        for table_obj in available_tables_objects:
            reservations_on_target_table_same_day_shift = [
                res.to_dict() for res in manager.load_reservations()
                if res.table_id == table_obj.id and \
                   res.date == original_reservation.date and \
                   res.shift == original_reservation.shift and \
                   res.id != original_reservation.id
            ]
            available_tables_data.append({
                "id": table_obj.id,
                "display_name": table_obj.display_name,
                "capacity": table_obj.capacity,
                "existing_reservations_at_other_times": sorted(
                    [{'time': r['time'], 'name': r['name']} for r in reservations_on_target_table_same_day_shift],
                    key=lambda x: x['time']
                )
            })

        return jsonify({
            "success": True,
            "available_tables": available_tables_data,
            "original_reservation_details": {
                "name": original_reservation.name,
                "persons": original_reservation.persons,
                "date": original_reservation.date,
                "time": original_reservation.time,
                "shift": original_reservation.shift
            }
        })
    except Exception as e:
        app.logger.error(f"Fehler in api_get_available_tables_for_move: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Serverfehler: {e}"}), 500


@app.route('/api/move_reservation/<string:reservation_id>', methods=['POST'])
def api_move_reservation(reservation_id):
    data = request.get_json()
    if not data or 'new_table_id' not in data:
        return jsonify({"success": False, "message": "Fehlende 'new_table_id' im Request."}), 400

    new_table_id = data['new_table_id']

    try:
        moved_reservation = manager.move_reservation(reservation_id, new_table_id)
        if moved_reservation:
            return jsonify({
                "success": True,
                "message": f"Reservierung erfolgreich auf Tisch {get_table_display_name_by_id(new_table_id)} verschoben.",
                "moved_reservation": moved_reservation.to_dict()
            })
        else:
            return jsonify({"success": False,
                            "message": "Reservierung konnte nicht verschoben werden. Entweder nicht gefunden oder der Ziel-Tisch ist nicht verfügbar."}), 409
    except Exception as e:
        app.logger.error(f"Fehler in api_move_reservation: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Serverfehler beim Verschieben der Reservierung: {e}"}), 500


@app.route('/api/reservierung_angekommen/<string:reservation_id>', methods=['POST'])
def api_toggle_arrival(reservation_id):
    updated_reservation = manager.toggle_arrival_status(reservation_id)
    if updated_reservation:
        return jsonify({
            "success": True,
            "message": "Ankunftsstatus aktualisiert.",
            "reservation_id": updated_reservation.id,
            "arrived": updated_reservation.arrived
        })
    else:
        return jsonify({"success": False, "message": "Reservierung nicht gefunden."}), 404

@app.route('/api/reservierung_gegangen/<string:reservation_id>', methods=['POST'])
def api_mark_as_departed(reservation_id):
    """
    API-Endpunkt, um eine Reservierung als 'gegangen' zu markieren.
    """
    if not reservation_id:
        return jsonify({"success": False, "message": "Keine Reservierungs-ID angegeben."}), 400

    updated_reservation = manager.mark_as_departed(reservation_id)

    if updated_reservation:
        return jsonify({
            "success": True,
            "message": f"Reservierung für '{updated_reservation.name}' als gegangen markiert.",
            "reservation_id": updated_reservation.id,
            "arrived": updated_reservation.arrived, # Sende auch den arrived Status mit
            "departed": updated_reservation.departed
        })
    else:
        reservation_check = manager.get_reservation_by_id(reservation_id)
        if not reservation_check:
            message = "Reservierung nicht gefunden."
            status_code = 404
        elif reservation_check.departed:
            message = "Reservierung war bereits als gegangen markiert."
            status_code = 409 # Conflict, da bereits im gewünschten Zustand
        else:
            message = "Fehler beim Markieren der Reservierung als gegangen."
            status_code = 500 # Allgemeiner Serverfehler

        return jsonify({"success": False, "message": message}), status_code


@app.route('/zimmer')
def rooms_index():
    current_date_obj = datetime.date.today()
    default_date_str = current_date_obj.strftime("%Y-%m-%d")
    selected_date_str = request.args.get('date', default_date_str)

    # Schicht ist bei Zimmern meistens egal, aber wir behalten die Logik bei,
    # damit das System konsistent bleibt. Standardmäßig "Abend" (oder man könnte "Nacht" nennen).
    selected_shift = request.args.get('shift', Reservation.SHIFT_DINNER)

    all_reservations_objects = manager.load_reservations()

    # Filter Reservierungen für den Tag
    reservations_for_date = [r for r in all_reservations_objects
                             if r.date == selected_date_str and r.shift == selected_shift]

    display_rooms_data = []

    # Hier iterieren wir über ALL_ROOMS statt ALL_TABLES
    for room_model in ALL_ROOMS:
        room_data = {
            'id': room_model.id,
            'area': room_model.area,
            'capacity': room_model.capacity,
            'display_name': room_model.display_name,
            'type': room_model.type,
            'status': "frei",
            'reservations_on_table': []
        }

        is_occupied = False
        for res_obj in reservations_for_date:
            if res_obj.table_id == room_model.id:
                room_data['reservations_on_table'].append({
                    'id': res_obj.id,
                    'name': res_obj.name,
                    'time': res_obj.time,
                    'persons': res_obj.persons,
                    'info': res_obj.info,
                    'arrived': res_obj.arrived,
                    'departed': getattr(res_obj, 'departed', False)
                })
                # Wenn jemand drauf ist, ist das Zimmer belegt
                if not getattr(res_obj, 'departed', False):
                    is_occupied = True

        if is_occupied:
            room_data['status'] = 'belegt'

        display_rooms_data.append(room_data)

    return render_template(
        'rooms.html',  # Neues Template
        rooms=display_rooms_data,
        selected_date=selected_date_str,
        selected_shift=selected_shift,
        valid_shifts=Reservation.VALID_SHIFTS
    )

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5001)
    pass
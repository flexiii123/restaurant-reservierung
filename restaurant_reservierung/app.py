from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import datetime, os
from datetime import timedelta
from core import manager
from core.models import ALL_TABLES, Reservation, Reservation as ResModel
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
    for t in ALL_TABLES:
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
    table_name = request.args.get('table_name',
                                  get_table_display_name_by_id(table_id) if table_id else "Gewünschter Tisch")

    selected_date_from_url = request.args.get('date')
    final_selected_date = datetime.date.today().strftime("%Y-%m-%d")
    if selected_date_from_url:
        try:
            datetime.datetime.strptime(selected_date_from_url, "%Y-%m-%d")
            final_selected_date = selected_date_from_url
        except ValueError:
            app.logger.warning(f"Ungültiges Datumsformat im GET-Request für /reservieren: {selected_date_from_url}")

    current_shift_from_url = request.args.get('shift', Reservation.SHIFT_DINNER)
    if current_shift_from_url not in Reservation.VALID_SHIFTS:
        current_shift_from_url = Reservation.SHIFT_DINNER

    possible_times_for_current_shift = []
    if current_shift_from_url == Reservation.SHIFT_LUNCH:
        possible_times_for_current_shift = generate_time_slots(start_hour=11, start_minute=0,
                                                               end_hour=14, end_minute=0,
                                                               interval_minutes=15)
    elif current_shift_from_url == Reservation.SHIFT_DINNER:
        possible_times_for_current_shift = generate_time_slots(start_hour=17, start_minute=0,
                                                               end_hour=22, end_minute=0,
                                                               interval_minutes=15)

    available_times = []
    if table_id:
        for time_slot in possible_times_for_current_shift:
            if manager.is_table_available_for_specific_reservation_time(
                    table_id_to_check=table_id,
                    date_str_to_check=final_selected_date,
                    time_str_to_check=time_slot,
                    shift_to_check=current_shift_from_url
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
        if manager.is_table_available_for_specific_reservation_time(
                table_id_to_check=reservation_object.table_id,
                date_str_to_check=reservation_object.date,
                time_str_to_check=time_slot,
                shift_to_check=reservation_object.shift,
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
    filter_date_param = request.args.get('filter_date')
    filter_shift_param = request.args.get('shift', Reservation.SHIFT_DINNER)

    if filter_shift_param not in Reservation.VALID_SHIFTS:
        filter_shift_param = Reservation.SHIFT_DINNER

    current_date_obj = datetime.date.today()
    today_str = current_date_obj.strftime("%Y-%m-%d")

    min_filter_date_obj = current_date_obj - timedelta(days=manager.MAX_RESERVATION_AGE_DAYS)
    min_filter_date_str = min_filter_date_obj.strftime("%Y-%m-%d")

    def format_date_european_local(date_str_yyyy_mm_dd):
        if not date_str_yyyy_mm_dd: return ""
        try:
            dt_obj = datetime.datetime.strptime(date_str_yyyy_mm_dd, "%Y-%m-%d")
            return dt_obj.strftime("%d.%m.%Y")
        except ValueError:
            return date_str_yyyy_mm_dd

    def get_table_display_name_by_id_local(table_id_to_find):
        for t_model in ALL_TABLES:  # Stelle sicher, dass ALL_TABLES importiert ist (from core.models import ALL_TABLES)
            if t_model.id == table_id_to_find:
                return t_model.display_name
        return table_id_to_find

    all_raw_reservations = manager.load_reservations()
    reservations_processed = []

    for res_obj in all_raw_reservations:
        if isinstance(res_obj, Reservation):
            try:
                res_date_obj_loop = datetime.datetime.strptime(res_obj.date, "%Y-%m-%d").date()
                if res_date_obj_loop >= min_filter_date_obj:
                    res_dict = res_obj.to_dict()
                    if res_dict.get('date'):
                        res_dict['table_display_name'] = get_table_display_name_by_id_local(res_obj.table_id)
                        res_dict['display_date'] = format_date_european_local(res_obj.date)
                        reservations_processed.append(res_dict)
            except ValueError:
                app.logger.warning(f"Reservierung {res_obj.id} mit ungültigem Datum {res_obj.date} wird übersprungen.")

    current_page_reservations_unfiltered_by_shift = []
    page_title_date_part = ""
    active_picker_date = today_str
    today_display = format_date_european_local(today_str)

    if filter_date_param is None:
        current_page_reservations_unfiltered_by_shift = [r for r in reservations_processed if
                                                         r.get('date') == today_str]
        page_title_date_part = f"für heute {filter_shift_param.capitalize()}, den {today_display}"
        active_picker_date = today_str
    elif filter_date_param == "":
        current_page_reservations_unfiltered_by_shift = [r for r in reservations_processed if
                                                         r.get('date') >= today_str]
        page_title_date_part = "für alle zukünftigen Termine (ab heute)"
        active_picker_date = ""
    else:
        try:
            datetime.datetime.strptime(filter_date_param, "%Y-%m-%d")
            current_page_reservations_unfiltered_by_shift = [r for r in reservations_processed if
                                                             r.get('date') == filter_date_param]
            selected_date_display = format_date_european_local(filter_date_param)
            page_title_date_part = f"für den {selected_date_display} ({filter_shift_param})"
            if filter_date_param == today_str:
                page_title_date_part = f"für heute {filter_shift_param}, den {selected_date_display}"
            active_picker_date = filter_date_param
        except ValueError:
            current_page_reservations_unfiltered_by_shift = [r for r in reservations_processed if
                                                             r.get('date') == today_str]
            page_title_date_part = f"für heute {filter_shift_param}, den {today_display} (ungültiger Datumsfilter)"
            active_picker_date = today_str

    current_page_reservations = [
        r for r in current_page_reservations_unfiltered_by_shift
        if r.get('shift') == filter_shift_param
    ]

    page_title = f"Reservierungen {page_title_date_part}"

    sort_by_param = request.args.get('sort_by', 'table_display_name')
    sort_order_param = request.args.get('order', 'asc')

    if sort_order_param not in ['asc', 'desc']:
        sort_order_param = 'asc'
    reverse_order = (sort_order_param == 'desc')

    if sort_by_param == 'name':
        current_page_reservations.sort(key=lambda r: str(r.get('name', '')).lower(), reverse=reverse_order)
    elif sort_by_param == 'table_display_name':
        current_page_reservations.sort(key=lambda r: str(r.get('table_display_name', '')).lower(),
                                       reverse=reverse_order)
    elif sort_by_param == 'date':
        current_page_reservations.sort(key=lambda r: str(r.get('date', '')), reverse=reverse_order)
    elif sort_by_param == 'time':
        def time_sort_key(reservation_dict):
            time_str = reservation_dict.get('time', '00:00')
            try:
                h, m = map(int, time_str.split(':'))
                return datetime.time(h, m)
            except ValueError:
                return datetime.time(0, 0)

        current_page_reservations.sort(key=time_sort_key, reverse=reverse_order)
    elif sort_by_param == 'persons':
        current_page_reservations.sort(key=lambda r: int(r.get('persons', 0)), reverse=reverse_order)
    else:
        current_page_reservations.sort(key=lambda r: str(r.get('date', '')), reverse=reverse_order)

    sortable_columns = ['name', 'table_display_name', 'date', 'time', 'persons']
    next_sort_order_dict = {}
    for col_key in sortable_columns:
        if sort_by_param == col_key:
            next_sort_order_dict[col_key] = 'desc' if sort_order_param == 'asc' else 'asc'
        else:
            next_sort_order_dict[col_key] = 'asc'

    return render_template(
        'reservations_list.html',
        reservations=current_page_reservations,
        active_filter_date=active_picker_date,
        page_title=page_title,
        current_sort_by=sort_by_param,
        current_sort_order=sort_order_param,
        next_sort_order=next_sort_order_dict,
        min_filter_date=min_filter_date_str,
        available_shifts=Reservation.VALID_SHIFTS,
        current_filter_shift=filter_shift_param
    )

@app.route('/api/neue_reservierung', methods=['POST'])
def api_create_reservation():
    if request.method == 'GET':
        return "GET request received by /api/neue_reservierung"
    try:
        data = request.get_json()
        if not data or not all(k in data for k in ("name", "date", "time", "persons", "table_id", "shift")):
            return jsonify({"success": False, "message": "Fehlende oder ungültige Daten."}), 400

        if data['shift'] not in ResModel.VALID_SHIFTS:
            return jsonify({"success": False, "message": f"Ungültiger Schichtwert: {data['shift']}."}), 400

        try:
            datetime.datetime.strptime(data['date'], "%Y-%m-%d")
        except ValueError:
            return jsonify({"success": False, "message": "Ungültiges Datumsformat. Bitte YYYY-MM-DD verwenden."}), 400

        if not manager.is_table_available_for_specific_reservation_time(
                table_id_to_check=data['table_id'],
                date_str_to_check=data['date'],
                time_str_to_check=data['time'],
                shift_to_check=data['shift']
        ):
            return jsonify({"success": False, "message": "Der Tisch ist zur gewählten Zeit bereits belegt."}), 409

        new_reservation = manager.create_reservation(
            name=data['name'],
            date_str=data['date'],
            time_str=data['time'],
            persons=int(data['persons']),
            table_id=data['table_id'],
            info=data.get('info', ""),
            shift=data['shift']
        )
        if new_reservation:
            return jsonify({
                "success": True,
                "message": "Reservierung erfolgreich erstellt!",
                "reservation_id": new_reservation.id,
                "redirect_url": url_for('index', date=data['date'], shift=data['shift'])
            })
        else:
            return jsonify({"success": False, "message": "Fehler beim Erstellen der Reservierung auf dem Server."}), 500
    except ValueError as ve:
        return jsonify({"success": False, "message": f"Ungültige Eingabe: {ve}"}), 400
    except Exception as e:
        app.logger.error(f"Fehler in api_create_reservation: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Serverfehler: {e}"}), 500


@app.route('/api/reservierung_bearbeiten/<string:reservation_id>', methods=['POST'])
def api_update_reservation(reservation_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "Keine Daten empfangen."}), 400

        shift_value_from_payload = data.get('shift')
        if shift_value_from_payload is not None and shift_value_from_payload not in ResModel.VALID_SHIFTS:
            return jsonify({"success": False, "message": f"Ungültiger Schichtwert: {shift_value_from_payload}."}), 400

        date_from_payload = data.get('date')
        if date_from_payload:
            try:
                datetime.datetime.strptime(date_from_payload, "%Y-%m-%d")
            except ValueError:
                return jsonify({"success": False,
                                "message": "Ungültiges Datumsformat für das Update. Bitte YYYY-MM-DD verwenden."}), 400

        original_res = manager.get_reservation_by_id(reservation_id)
        if not original_res:
            return jsonify({"success": False, "message": "Originalreservierung nicht gefunden."}), 404

        target_table_id = data.get('table_id', original_res.table_id)
        target_date = data.get('date', original_res.date)
        target_time = data.get('time', original_res.time)
        target_shift = data.get('shift', original_res.shift)

        if (target_table_id != original_res.table_id or \
                target_date != original_res.date or \
                target_time != original_res.time or \
                target_shift != original_res.shift):
            if not manager.is_table_available_for_specific_reservation_time(
                    table_id_to_check=target_table_id,
                    date_str_to_check=target_date,
                    time_str_to_check=target_time,
                    shift_to_check=target_shift,
                    reservation_id_to_ignore=reservation_id):
                return jsonify({"success": False,
                                "message": f"Der Tisch ist zur gewählten Zeit/Datum/Schicht bereits belegt."}), 409

        updated_reservation = manager.update_reservation(
            reservation_id_to_update=reservation_id,
            name=data.get('name'),
            date_str=data.get('date'),
            time_str=data.get('time'),
            persons=int(data.get('persons')) if data.get('persons') is not None else None,
            table_id=data.get('table_id'),
            info=data.get('info'),
            shift=shift_value_from_payload
        )

        if updated_reservation:
            return jsonify({
                "success": True,
                "message": "Reservierung erfolgreich aktualisiert.",
                "redirect_url": url_for('reservations_list_page', filter_date=updated_reservation.date)
            })
        else:
            return jsonify(
                {"success": False, "message": "Fehler beim Aktualisieren oder Reservierung nicht gefunden."}), 404
    except ValueError as ve:
        return jsonify({"success": False, "message": f"Ungültige Eingabe bei Aktualisierung: {ve}"}), 400
    except Exception as e:
        app.logger.error(f"Fehler in api_update_reservation für ID {reservation_id}: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Serverfehler: {e}"}), 500


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

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5001)
    pass
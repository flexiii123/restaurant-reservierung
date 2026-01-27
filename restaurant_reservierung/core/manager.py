import json
import os
import shutil
import glob
from datetime import datetime, date, timedelta
from .models import Reservation, ALL_RESOURCES
import tempfile
import logging

from .models import Reservation

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE_DIR, 'data', 'reservations.json')
BACKUP_DIR = os.path.join(BASE_DIR, 'data', 'backups')
MAX_BACKUPS_TO_KEEP = 10
MAX_RESERVATION_AGE_DAYS = 7

_cached_reservations = None
_reservations_loaded_at_least_once = False

def ensure_backup_dir_exists():
    if not os.path.exists(BACKUP_DIR):
        try:
            os.makedirs(BACKUP_DIR)
            logger.info(f"Backup-Verzeichnis erstellt: {BACKUP_DIR}")
        except OSError as e:
            logger.error(f"Fehler beim Erstellen des Backup-Verzeichnisses {BACKUP_DIR}: {e}")
            return False
    return True

def cleanup_old_backups():
    if not ensure_backup_dir_exists():
        return
    try:
        backup_files = glob.glob(os.path.join(BACKUP_DIR, "reservations_backup_*.json"))
        backup_files.sort(key=os.path.getmtime)
        if len(backup_files) > MAX_BACKUPS_TO_KEEP:
            files_to_delete = backup_files[:-MAX_BACKUPS_TO_KEEP]
            for f_del in files_to_delete:
                try:
                    os.remove(f_del)
                except OSError as e:
                    logger.error(f"Fehler beim Löschen der alten Backup-Datei {f_del}: {e}")
    except Exception as e:
        logger.error(f"Fehler beim Aufräumen alter Backups: {e}")

def load_latest_valid_backup():
    if not os.path.exists(BACKUP_DIR):
        logger.warning("Backup-Verzeichnis nicht gefunden, kann kein Backup wiederherstellen.")
        return None, None
    try:
        backup_files = glob.glob(os.path.join(BACKUP_DIR, "reservations_backup_*.json"))
        if not backup_files:
            logger.info("Keine Backup-Dateien im Backup-Verzeichnis gefunden.")
            return None, None
        backup_files.sort(key=os.path.getmtime, reverse=True)
        for backup_file_path in backup_files:
            logger.info(f"Versuche, Backup-Datei zu laden: {backup_file_path}")
            try:
                with open(backup_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if not content.strip():
                        logger.warning(f"Backup-Datei {backup_file_path} ist leer. Überspringe.")
                        continue
                    reservations_data = json.loads(content)
                if isinstance(reservations_data, list):
                    if reservations_data and not isinstance(Reservation.from_dict(reservations_data[0]), Reservation):
                        logger.warning(
                            f"Backup-Datei {backup_file_path} scheint keine gültigen Reservierungsdaten zu enthalten (Objekt-Test fehlgeschlagen). Überspringe.")
                        continue
                    elif not reservations_data:
                        pass
                    logger.info(f"Gültiges Backup gefunden und geladen: {backup_file_path}")
                    return reservations_data, backup_file_path
                else:
                    logger.warning(
                        f"Backup-Datei {backup_file_path} hat nicht das erwartete Listenformat. Überspringe.")
            except json.JSONDecodeError:
                logger.warning(f"Backup-Datei {backup_file_path} ist korrupt (JSONDecodeError). Überspringe.")
            except ValueError as ve:
                logger.warning(
                    f"Fehler beim Validieren des Inhalts der Backup-Datei {backup_file_path}: {ve}. Überspringe.")
            except Exception as e:
                logger.error(
                    f"Unerwarteter Fehler beim Laden/Prüfen der Backup-Datei {backup_file_path}: {e}. Überspringe.")
        logger.warning("Kein gültiges, lesbares Backup im Backup-Verzeichnis gefunden.")
        return None, None
    except Exception as e:
        logger.error(f"Fehler beim Suchen/Sortieren von Backup-Dateien: {e}")
        return None, None

def _load_reservations_from_disk():
    global _reservations_loaded_at_least_once
    reservations_data = None
    loaded_from_backup_path = None

    if not os.path.exists(DATA_FILE):
        logger.warning(f"Haupt-Reservierungsdatei {DATA_FILE} nicht gefunden.")
        reservations_data, loaded_from_backup_path = load_latest_valid_backup()
        if reservations_data is None:
            logger.warning("Konnte weder Hauptdatei noch Backup finden/laden. Erstelle neue leere Reservierungsliste.")
            try:
                with open(DATA_FILE, 'w', encoding='utf-8') as f:
                    json.dump([], f)
                logger.info(f"Leere Reservierungsdatei {DATA_FILE} erstellt.")
            except Exception as e_create:
                logger.error(f"Konnte leere Reservierungsdatei {DATA_FILE} nicht erstellen: {e_create}")
            return []
    else:
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content.strip():
                    logger.warning(f"Haupt-Reservierungsdatei {DATA_FILE} ist leer.")
                    reservations_data, loaded_from_backup_path = load_latest_valid_backup()
                    if reservations_data is None:
                        logger.warning("Hauptdatei leer und kein Backup gefunden. Verwende leere Liste.")
                        return []
                else:
                    reservations_data = json.loads(content)
                    logger.info(f"Reservierungen erfolgreich aus Hauptdatei {DATA_FILE} geladen.")
        except json.JSONDecodeError as e:
            logger.error(f"Haupt-Reservierungsdatei {DATA_FILE} ist korrupt (JSONDecodeError): {e}.")
            reservations_data, loaded_from_backup_path = load_latest_valid_backup()
            if reservations_data is None:
                logger.critical(
                    f"KRITISCH: Hauptdatei korrupt und KEIN gültiges Backup gefunden! Starte mit leerer Liste.")
                try:
                    os.rename(DATA_FILE, DATA_FILE + f".corrupt_{datetime.now().strftime('%Y%m%d%H%M%S')}")
                    with open(DATA_FILE, 'w', encoding='utf-8') as f:
                        json.dump([], f)
                except Exception:
                    pass
                return []
        except Exception as e:
            logger.error(f"Unerwarteter FEHLER beim Laden von {DATA_FILE}: {e}. Versuche Backup.")
            reservations_data, loaded_from_backup_path = load_latest_valid_backup()
            if reservations_data is None:
                logger.critical(
                    f"KRITISCH: Hauptdatei konnte nicht gelesen werden und KEIN gültiges Backup gefunden! Starte mit leerer Liste.")
                return []

    if loaded_from_backup_path and reservations_data is not None:
        logger.warning(f"Stelle {DATA_FILE} aus Backup {loaded_from_backup_path} wieder her.")
        try:
            if os.path.exists(DATA_FILE):
                corrupt_backup_name = DATA_FILE + f".corrupted_before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.move(DATA_FILE, corrupt_backup_name)
                logger.info(f"Originale (möglicherweise korrupte) Datei gesichert als: {corrupt_backup_name}")
            shutil.copy2(loaded_from_backup_path, DATA_FILE)
            logger.info(f"{DATA_FILE} erfolgreich aus Backup wiederhergestellt.")
        except Exception as e_restore:
            logger.error(
                f"FEHLER beim Wiederherstellen von {DATA_FILE} aus Backup {loaded_from_backup_path}: {e_restore}")

    loaded_objects = []
    if reservations_data:
        for r_data in reservations_data:
            try:
                loaded_objects.append(Reservation.from_dict(r_data))
            except ValueError as ve:
                logger.error(f"FEHLER beim Parsen einer Reservierung aus geladenen Daten: {ve} - Daten: {r_data}")
            except Exception as e_obj:
                logger.error(f"Unerwarteter Fehler bei Erstellung eines Reservation-Objekts: {e_obj} - Daten: {r_data}")
    _reservations_loaded_at_least_once = True
    return loaded_objects

def load_reservations(force_reload=False):
    global _cached_reservations
    if force_reload or not _reservations_loaded_at_least_once or _cached_reservations is None:
        logger.info("Lade Reservierungen von Festplatte (force_reload oder Erstladung)...")
        _cached_reservations = _load_reservations_from_disk()
    return list(_cached_reservations)

def save_reservations(reservations_objects_list):
    global _cached_reservations
    if not ensure_backup_dir_exists():
        logger.warning("Backup-Verzeichnis nicht verfügbar. Speichere ohne Backup der Originaldatei.")
    else:
        if os.path.exists(DATA_FILE):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_file_name = f"reservations_backup_{timestamp}.json"
            backup_file_path = os.path.join(BACKUP_DIR, backup_file_name)
            try:
                shutil.copy2(DATA_FILE, backup_file_path)
                cleanup_old_backups()
            except Exception as e:
                logger.error(f"Fehler beim Erstellen des Backups von {DATA_FILE}: {e}")
    try:
        temp_fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(DATA_FILE), prefix='res_temp_', suffix='.json')
        reservations_as_dicts = [r.to_dict() for r in reservations_objects_list]
        with os.fdopen(temp_fd, 'w', encoding='utf-8') as tmp:
            json.dump(reservations_as_dicts, tmp, indent=4)
        os.replace(temp_path, DATA_FILE)
        _cached_reservations = list(reservations_objects_list)
    except Exception as e:
        logger.error(f"FEHLER beim Speichern von Reservierungen: {e}")
        if 'temp_path' in locals() and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError as e_rem:
                logger.warning(f"Konnte temporäre Datei {temp_path} nicht löschen: {e_rem}")


def cleanup_old_reservations():
    res = load_reservations()
    limit = date.today() - timedelta(days=7)  # date.today() nutzen
    new_res = []
    for r in res:
        try:
            # Hier nutzen wir datetime.strptime, weil wir String parsen
            if datetime.strptime(r.date, "%Y-%m-%d").date() >= limit:
                new_res.append(r)
        except ValueError:
            new_res.append(r)

    if len(new_res) < len(res): save_reservations(new_res)

import uuid


def create_reservation(name, date, time, persons, table_id, info, shift, end_date=None):
    res = load_reservations()
    # Wenn kein end_date angegeben, ist es = date (für Tische)
    if not end_date: end_date = date

    new_r = Reservation(str(uuid.uuid4()), name, date, time, persons, table_id, info, shift=shift,
                        end_date_str=end_date)
    res.append(new_r)
    save_reservations(res)
    return new_r


def is_room_available(room_id, checkin_str, checkout_str, ignore_id=None):
    # Wir nutzen datetime.strptime direkt (ohne datetime.datetime...)
    try:
        checkin = datetime.strptime(checkin_str, "%Y-%m-%d").date()
        checkout = datetime.strptime(checkout_str, "%Y-%m-%d").date()
    except ValueError:
        return False

    for r in load_reservations():
        if r.table_id == room_id and r.id != ignore_id:
            try:
                r_start = datetime.strptime(r.date, "%Y-%m-%d").date()
                end_str = getattr(r, 'end_date', None)
                if end_str:
                    r_end = datetime.strptime(end_str, "%Y-%m-%d").date()
                else:
                    r_end = r_start

                # Überschneidungslogik
                if checkin < r_end and checkout > r_start:
                    return False
            except ValueError:
                continue
    return True

def get_reservation_by_id(reservation_id_to_find):
    all_reservations = load_reservations()
    for res in all_reservations:
        if res.id == reservation_id_to_find:
            return res
    return None

def update_reservation(reservation_id_to_update, name=None, date_str=None, time_str=None, persons=None, table_id=None,
                       info=None, shift=None):
    all_reservations = load_reservations()
    target_reservation = None
    updated = False
    for i, res in enumerate(all_reservations):
        if res.id == reservation_id_to_update:
            target_reservation = res
            if name is not None and res.name != name: res.name = name; updated = True
            if date_str is not None and res.date != date_str: res.date = date_str; updated = True
            if time_str is not None and res.time != time_str: res.time = time_str; updated = True
            if persons is not None:
                try:
                    persons_int = int(persons)
                    if res.persons != persons_int: res.persons = persons_int; updated = True
                except ValueError:
                    logger.warning(f"Ungültige Personenzahl '{persons}' für Update ignoriert.")
            if table_id is not None and res.table_id != table_id: res.table_id = table_id; updated = True
            if info is not None and res.info != info: res.info = info; updated = True
            if shift is not None and shift in Reservation.VALID_SHIFTS and res.shift != shift:
                res.shift = shift;
                updated = True
            elif shift is not None:
                logger.warning(f"Ungültiger Shift '{shift}' für Update ignoriert.")

            if updated:
                all_reservations[
                    i] = res
                save_reservations(all_reservations)
            return res
    return None

def delete_reservation(reservation_id_to_delete):
    all_reservations = load_reservations()
    initial_length = len(all_reservations)
    updated_reservations = [res for res in all_reservations if res.id != reservation_id_to_delete]
    if len(updated_reservations) < initial_length:
        save_reservations(updated_reservations)
        return True
    return False

def get_reservations_on_table_at_datetime_and_shift(table_id_to_check, date_str_to_check, time_str_to_check,
                                                    shift_to_check):
    all_reservations = load_reservations()
    conflicting_reservations = []
    for res in all_reservations:
        if (res.table_id == table_id_to_check and
                res.date == date_str_to_check and
                res.shift == shift_to_check and
                res.time == time_str_to_check):
            conflicting_reservations.append(res)
    return conflicting_reservations


def is_table_available_for_specific_reservation_time(table_id, date, time, shift, reservation_id_to_ignore=None):
    # Wenn es ein Zimmer ist, nutzen wir die neue Logik NICHT HIER, sondern rufen is_room_available auf
    if "zimmer" in table_id:
        return True  # Hier dummy true, weil wir das im API Endpunkt anders regeln müssen

    for r in load_reservations():
        if r.table_id == table_id and r.date == date and r.time == time and r.shift == shift:
            if r.id != reservation_id_to_ignore: return False
    return True

from .models import ALL_TABLES, ALL_RESOURCES
from datetime import timedelta

def get_available_tables_for_moving(original_res):
    available = []
    for t in ALL_RESOURCES:
        if t.id == original_res.table_id: continue
        # Wenn es ein Zimmer ist, prüfen wir den Zeitraum
        if "zimmer" in t.id and "zimmer" in original_res.table_id:
             if is_room_available(t.id, original_res.date, original_res.end_date, original_res.id):
                 available.append(t)
        # Sonst normale Tischprüfung
        elif is_table_available_for_specific_reservation_time(t.id, original_res.date, original_res.time, original_res.shift, original_res.id):
            available.append(t)
    return available


def move_reservation(rid, new_tid):
    r = get_reservation_by_id(rid)
    if not r: return None

    # Check ob Ziel frei ist
    is_free = False
    if "zimmer" in new_tid:
        is_free = is_room_available(new_tid, r.date, r.end_date, rid)
    else:
        is_free = is_table_available_for_specific_reservation_time(new_tid, r.date, r.time, r.shift, rid)

    if is_free:
        r.table_id = new_tid
        return update_reservation(rid, r.name, r.date, r.time, r.persons, new_tid, r.info, r.shift)
    return None

def toggle_arrival_status(reservation_id):
    all_reservations = load_reservations()
    reservation_updated = None
    for i, res in enumerate(all_reservations):
        if res.id == reservation_id:
            res.arrived = not res.arrived
            all_reservations[i] = res
            save_reservations(all_reservations)
            return res
    return None

def mark_as_departed(reservation_id):
    all_reservations = load_reservations()
    for i, res in enumerate(all_reservations):
        if res.id == reservation_id:
            if not res.arrived and not res.departed:
                logger.warning(
                    f"Gast {res.name} (ID: {reservation_id}) war nicht als angekommen markiert, wird aber als gegangen gesetzt.")
                res.arrived = True

            if res.departed:
                logger.info(f"Gast {res.name} (ID: {reservation_id}) ist bereits als gegangen markiert.")
                return res

            res.departed = True
            all_reservations[i] = res
            save_reservations(all_reservations)
            logger.info(f"Gast {res.name} (ID: {reservation_id}) als gegangen markiert.")
            return res
    logger.error(f"Reservierung {reservation_id} nicht gefunden, um als gegangen zu markieren.")
    return None
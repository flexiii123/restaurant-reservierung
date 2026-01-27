import json
import os
import shutil
import glob
from datetime import datetime
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
    all_reservations = load_reservations(force_reload=True)
    if not all_reservations:
        return False
    today = datetime.now().date()

    min_allowed_date = today - timedelta(days=MAX_RESERVATION_AGE_DAYS)
    valid_reservations = []
    deleted_count = 0
    for res in all_reservations:
        try:
            res_date_obj = datetime.strptime(res.date, "%Y-%m-%d").date()
            if res_date_obj >= min_allowed_date:
                valid_reservations.append(res)
            else:
                deleted_count += 1
                logger.info(f"Entferne alte Reservierung: ID {res.id}, Gast: {res.name}, Datum: {res.date}")
        except ValueError:
            logger.warning(
                f"Reservierung mit ID {res.id} hat ungültiges Datumsformat '{res.date}'. Wird bei Bereinigung behalten.")
            valid_reservations.append(res)
    if deleted_count > 0:
        logger.info(
            f"Automatische Bereinigung: {deleted_count} Reservierung(en) älter als {MAX_RESERVATION_AGE_DAYS} Tage entfernt.")
        save_reservations(valid_reservations)
        return True
    else:
        logger.info("Keine alten Reservierungen zum Bereinigen gefunden.")
        return False

import uuid

def create_reservation(name, date_str, time_str, persons, table_id, info="", shift=Reservation.SHIFT_DINNER):
    reservations = load_reservations()
    new_id = str(uuid.uuid4())
    new_reservation = Reservation(
        reservation_id=new_id, name=name, date_str=date_str, time_str=time_str,
        persons=persons, table_id=table_id, info=info, shift=shift
    )
    reservations.append(new_reservation)
    save_reservations(reservations)
    return new_reservation


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

def is_table_available_for_specific_reservation_time(table_id_to_check, date_str_to_check, time_str_to_check,
                                                     shift_to_check, reservation_id_to_ignore=None):
    reservations_at_slot = get_reservations_on_table_at_datetime_and_shift(table_id_to_check, date_str_to_check,
                                                                           time_str_to_check, shift_to_check)
    for res in reservations_at_slot:
        if res.id == reservation_id_to_ignore:
            continue
        return False
    return True

from .models import ALL_TABLES, ALL_RESOURCES
from datetime import timedelta

def get_available_tables_for_moving(original_reservation_obj):
    if not original_reservation_obj:
        return []
    available_tables = []
    for table_model in ALL_RESOURCES:
        if table_model.id == original_reservation_obj.table_id:
            continue
        if is_table_available_for_specific_reservation_time(
                table_id_to_check=table_model.id,
                date_str_to_check=original_reservation_obj.date,
                time_str_to_check=original_reservation_obj.time,
                shift_to_check=original_reservation_obj.shift,
                reservation_id_to_ignore=original_reservation_obj.id):
            available_tables.append(table_model)
    return available_tables

def move_reservation(reservation_id_to_move, new_table_id):
    all_reservations = load_reservations()
    reservation_to_move = None
    idx_to_move = -1

    for i, res in enumerate(all_reservations):
        if res.id == reservation_id_to_move:
            reservation_to_move = res
            idx_to_move = i
            break
    if not reservation_to_move:
        logger.warning(f"Verschieben fehlgeschlagen: Reservierung {reservation_id_to_move} nicht gefunden.")
        return None
    if not is_table_available_for_specific_reservation_time(
            table_id_to_check=new_table_id,
            date_str_to_check=reservation_to_move.date,
            time_str_to_check=reservation_to_move.time,
            shift_to_check=reservation_to_move.shift,
            reservation_id_to_ignore=reservation_id_to_move):
        logger.warning(
            f"Verschieben fehlgeschlagen: Ziel-Tisch {new_table_id} ist um {reservation_to_move.time} nicht verfügbar.")
        return None

    reservation_to_move.table_id = new_table_id
    all_reservations[idx_to_move] = reservation_to_move
    save_reservations(all_reservations)
    logger.info(f"Reservierung {reservation_id_to_move} erfolgreich auf Tisch {new_table_id} verschoben.")
    return reservation_to_move

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
import json
import os
import shutil
import glob
from datetime import datetime, date, timedelta
from .models import Reservation, ALL_RESOURCES, ALL_ROOMS
import tempfile
import logging

from .models import Reservation

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE_DIR, 'data', 'reservations.json')
MERGE_FILE = os.path.join(BASE_DIR, 'data', 'table_merges.json')
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
    limit = date.today() - timedelta(days=7)
    new_res = []
    for r in res:
        try:
            if datetime.strptime(r.date, "%Y-%m-%d").date() >= limit:
                new_res.append(r)
        except (ValueError, TypeError):
            # Falls Datum korrupt, behalten oder löschen?
            # Besser behalten und loggen, hier löschen wir es sicherheitshalber nicht
            # außer es ist extrem alt. Wir behalten es hier mal.
            new_res.append(r)

    if len(new_res) < len(res): save_reservations(new_res)

import uuid


def create_reservation(name, date, time, persons, table_id, info, shift, end_date=None, parent_id=None):
    res = load_reservations()
    my_id = str(uuid.uuid4())
    if not end_date: end_date = date

    # NEU: Wenn es eine Hauptbuchung ist, schauen wir nach Partnern
    # und schreiben deren Namen in die Info, damit man es in der Liste sieht.
    partners_display = ""
    merges = load_merges()

    if parent_id is None and table_id in merges:
        # Wir holen uns die Namen der Partner-Tische für die Anzeige (optional, aber schick)
        # (Da wir hier keinen Zugriff auf ALL_TABLES DisplayNames haben, lassen wir es im Info-Text
        #  oder lösen es später in app.py. Wir markieren es nur.)
        pass

    new_r = Reservation(my_id, name, date, time, persons, table_id, info, False, False, shift, end_date)

    if parent_id:
        new_r.info = f"[LINKED:{parent_id}] {info}"  # Markierung für Schattenbuchung

    res.append(new_r)
    save_reservations(res)

    # Schattenbuchungen erstellen
    if parent_id is None:
        if table_id in merges:
            partners = merges[table_id]
            for partner_id in partners:
                create_reservation(
                    name=f"{name}",  # Gleicher Name
                    date=date, time=time, persons=0,
                    table_id=partner_id,
                    info="Automatisch verbunden",
                    shift=shift, end_date=end_date,
                    parent_id=my_id
                )
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


def delete_reservation(rid):
    all_res = load_reservations()

    # Finde die zu löschende Reservierung
    target = None
    for r in all_res:
        if r.id == rid: target = r; break

    if not target: return False

    # Logik: Wir müssen die ID finden UND alle, die [LINKED:ID] in der Info haben
    new_res_list = []
    for r in all_res:
        # 1. Es ist die Reservierung selbst
        if r.id == rid: continue

        # 2. Es ist eine Schatten-Reservierung dieser ID (via Info Tag check)
        if f"[LINKED:{rid}]" in r.info: continue

        # 3. Falls wir eine Schatten-Reservierung löschen, sollten wir das Original löschen?
        # (Optional, hier löschen wir nur das angeklickte Element um Fehler zu vermeiden,
        # aber idealerweise löscht man immer den Parent)

        new_res_list.append(r)

    if len(new_res_list) < len(all_res):
        save_reservations(new_res_list)
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
    """
    Gibt verfügbare Ziele zurück.
    Logik:
    1. Wenn Zimmer -> Nur Zimmer anzeigen.
    2. Wenn Tisch -> Nur Tische anzeigen (keine Zimmer).
    3. Wenn Tisch-Gruppe -> Nur Gruppen gleicher Größe anzeigen.
    """
    if not original_res: return []

    available_tables = []
    merges = load_merges()

    # Prüfen: Ist der Ursprung ein Zimmer?
    source_is_room = "zimmer" in original_res.table_id.lower()

    # Prüfen: Wie groß ist die Ursprungsgruppe?
    source_partners = merges.get(original_res.table_id, [])
    source_group_size = 1 + len(source_partners)  # 1 (selbst) + Partner

    # Welche Liste durchsuchen wir?
    # Wenn Zimmer -> ALL_ROOMS, Wenn Tisch -> ALL_TABLES
    target_list = ALL_ROOMS if source_is_room else ALL_TABLES

    for target in target_list:
        # Sich selbst überspringen
        if target.id == original_res.table_id:
            continue

        # --- VERFÜGBARKEITS-CHECK ---
        is_free = False
        if source_is_room:
            # Zimmer-Check (Zeitraum)
            is_free = is_room_available(target.id, original_res.date, original_res.end_date, original_res.id)
        else:
            # Tisch-Check (Slot)
            is_free = is_table_available_for_specific_reservation_time(
                target.id, original_res.date, original_res.time, original_res.shift, original_res.id
            )

        if not is_free:
            continue

        # --- GRUPPEN-GRÖSSEN-CHECK (Nur für Tische relevant) ---
        if not source_is_room:
            target_partners = merges.get(target.id, [])
            target_group_size = 1 + len(target_partners)

            # Wenn Größen ungleich sind -> Überspringen
            # (z.B. Einzelner Tisch darf nicht auf 2er-Gruppe, 2er-Gruppe nicht auf Einzelnen)
            if source_group_size != target_group_size:
                continue

        available_tables.append(target)

    return available_tables


# core/manager.py

def move_reservation(rid, new_tid):
    """
    Verschiebt eine Reservierung.
    WICHTIG: Behandelt verbundene Tische (Schatten-Reservierungen).
    1. Löscht alte Schatten-Reservierungen auf den alten Partner-Tischen.
    2. Verschiebt die Haupt-Reservierung.
    3. Erstellt neue Schatten-Reservierungen auf den neuen Partner-Tischen (falls vorhanden).
    """
    # 1. Haupt-Reservierung holen
    r = get_reservation_by_id(rid)
    if not r:
        return None

    # Prüfen ob Ziel frei ist (Basis-Check)
    # Bei Zimmern nutzen wir is_room_available, bei Tischen den Slot-Check
    is_free = False
    if "zimmer" in new_tid.lower():
        is_free = is_room_available(new_tid, r.date, r.end_date, rid)
    else:
        is_free = is_table_available_for_specific_reservation_time(new_tid, r.date, r.time, r.shift, rid)

    if not is_free:
        return None

    # 2. Alte Schatten-Reservierungen löschen
    # Wir suchen alle Reservierungen, die diese ID als 'parent_id' im Info-Tag haben [LINKED:rid]
    all_res = load_reservations()
    res_to_keep = []
    linked_tag = f"[LINKED:{rid}]"

    for item in all_res:
        if linked_tag in item.info:
            # Das ist eine Schatten-Reservierung -> wir übernehmen sie NICHT in die neue Liste (löschen)
            continue
        res_to_keep.append(item)

    # Speichern, damit die alten Schatten weg sind
    save_reservations(res_to_keep)

    # 3. Haupt-Reservierung aktualisieren
    # Wir laden neu, da save_reservations oben den Cache geändert hat
    # Aber wir nutzen unser 'r' Objekt weiter und updaten es dann
    updated_r = update_reservation(rid, r.name, r.date, r.time, r.persons, new_tid, r.info, r.shift)

    # 4. Neue Schatten-Reservierungen erstellen (nur für Tische relevant, Zimmer werden selten gemerged)
    merges = load_merges()
    if new_tid in merges:
        partners = merges[new_tid]
        for partner_id in partners:
            # Prüfen ob Partner frei ist, wäre hier gut, aber wir erzwingen den Merge meistens.
            create_reservation(
                name=f"{r.name} (via {new_tid})",
                date=r.date,
                time=r.time,
                persons=0,
                table_id=partner_id,
                info="Automatisch verbunden",
                shift=r.shift,
                end_date=r.end_date,
                parent_id=rid  # WICHTIG: Neue Verlinkung zur Haupt-ID
            )

    return updated_r

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


def load_merges():
    """Lädt die Tisch-Verbindungen. Format: {'tisch_id': ['partner_tisch_id', ...]}"""
    if not os.path.exists(MERGE_FILE): return {}
    try:
        with open(MERGE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}


def save_merges(merges):
    dir_n = os.path.dirname(MERGE_FILE)
    if not os.path.exists(dir_n): os.makedirs(dir_n)
    with open(MERGE_FILE, 'w', encoding='utf-8') as f:
        json.dump(merges, f, indent=4)


# core/manager.py

def merge_tables(table_ids_list):
    """
    Verbindet eine LISTE von Tischen (z.B. ['tisch1', 'tisch2', 'tisch3']).
    """
    if len(table_ids_list) < 2: return False

    merges = load_merges()

    # 1. Wir bilden eine große Gruppe aus allen neuen Tischen
    # UND allen Tischen, die mit diesen bereits verbunden waren.
    new_group = set(table_ids_list)

    for tid in table_ids_list:
        if tid in merges:
            new_group.update(merges[tid])

    # 2. Speichern: Jeder Tisch in der Gruppe kennt alle anderen
    for member in new_group:
        partners = list(new_group)
        if member in partners:
            partners.remove(member)
        merges[member] = partners

    save_merges(merges)
    return True


def unmerge_tables(table_ids_list):
    """
    Löst eine LISTE von Tischen aus ihren Verbindungen.
    """
    if not table_ids_list: return False

    merges = load_merges()
    changed = False

    for table_id in table_ids_list:
        if table_id in merges:
            partners = merges[table_id]
            # Bei den Partnern diesen Tisch entfernen
            for p in partners:
                if p in merges and table_id in merges[p]:
                    merges[p].remove(table_id)
            # Eintrag löschen
            del merges[table_id]
            changed = True

    if changed:
        save_merges(merges)
        return True
    return False
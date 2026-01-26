const occupiedTableInfoModal = document.getElementById('occupiedTableInfoModal');
const occupiedTableModalMessageArea = document.getElementById('occupiedTableModalMessageArea');
const occupiedTableModalDetailsDiv = document.getElementById('occupiedTableModalDetails');
const modalTitleElement = occupiedTableInfoModal ? occupiedTableInfoModal.querySelector('h3') : null;

const deleteConfirmationModal = document.getElementById('deleteConfirmationModal');
const deleteModalMessageText = document.getElementById('deleteModalMessageText');
const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
const cancelDeleteBtn = document.getElementById('cancelDeleteBtn');
const deleteStatusModal = document.getElementById('deleteStatusModal');
const deleteStatusModalContent = deleteStatusModal ? deleteStatusModal.querySelector('.modal-content.modal-status-message') : null;

const moveReservationModal = document.getElementById('moveReservationModal');
const moveReservationGuestName = document.getElementById('moveReservationGuestName');
const moveReservationDetails = document.getElementById('moveReservationDetails');
const availableTablesListDiv = document.getElementById('availableTablesForMoveList');
const confirmMoveActionModal = document.getElementById('confirmMoveActionModal');
const confirmMoveActionModalText = document.getElementById('confirmMoveActionModalText');
const executeMoveBtn = document.getElementById('executeMoveBtn');
const cancelMoveActionBtn = document.getElementById('cancelMoveActionBtn');

const confirmAddResModal = document.getElementById('confirmAddReservationToOccupiedTableModal');
const confirmAddResModalTableName = document.getElementById('confirmAddReservationTableName');
const proceedWithReservationBtn = document.getElementById('proceedWithReservationBtn');
const cancelAddReservationBtn = document.getElementById('cancelAddReservationBtn');

let pendingTableNavigationDetails = null;
let currentReservationIdToDelete = null;
let activeFilterDateBeforeDelete = null;
let currentReservationToMoveId = null;
let pendingMoveDetails = null;
let currentReservationIdToMarkDeparted = null;
let currentDepartedButtonElement = null;

function handleTableClick(tableElement) {
    if (!tableElement) {
        console.error("FEHLER: tableElement ist null oder undefined!");
        return;
    }
    const tableId = tableElement.getAttribute('data-table-id');
    const tableNameStrong = tableElement.querySelector('strong');
    const tableName = tableNameStrong ? tableNameStrong.textContent : 'Unbekannter Tisch';
    const hasReservationsString = tableElement.getAttribute('data-has-reservations');
    const hasReservations = hasReservationsString === 'true';
    const datePicker = document.getElementById('reservationDate');
    const shiftPicker = document.getElementById('shiftPicker');

    if (!datePicker || !shiftPicker) {
        console.error("Fehler: Datums- (reservationDate) oder Schichtauswahl (shiftPicker) nicht im DOM gefunden.");
        alert("Ein Fehler ist aufgetreten. Bitte laden Sie die Seite neu.");
        return;
    }
    const selectedDate = datePicker.value;
    const selectedShift = shiftPicker.value;

    if (!selectedDate) {
        alert("Bitte wählen Sie zuerst ein Datum aus.");
        return;
    }
    if (!selectedShift) {
        alert("Bitte wählen Sie zuerst eine Schicht aus.");
        return;
    }
    pendingTableNavigationDetails = {
        tableId,
        tableName,
        selectedDate,
        selectedShift
    };
    if (hasReservations) {
        if (confirmAddResModal && confirmAddResModalTableName) {
            confirmAddResModalTableName.textContent = tableName;
            confirmAddResModal.classList.add('active');
        } else {
            console.error("FEHLER: Bestätigungsmodal ('confirmAddResModal') oder Tischnamen-Element ('confirmAddResModalTableName') wurde NICHT gefunden.");
            if (confirm(`Der Tisch "${tableName}" hat bereits Reservierungen. Fortfahren?`)) {
                navigateToReservationForm(pendingTableNavigationDetails);
            } else {
                pendingTableNavigationDetails = null;
            }
        }
    } else {
        navigateToReservationForm(pendingTableNavigationDetails);
    }
}

function navigateToReservationForm(details) {
    if (!details) {
        console.error("navigateToReservationForm: Keine Details zum Navigieren vorhanden!");
        return;
    }
    if (!details.tableId || !details.selectedDate || !details.selectedShift) {
        console.error("navigateToReservationForm: Unvollständige Details:", details);
        alert("Fehler: Es fehlen Informationen, um zur Reservierungsseite zu navigieren.");
        pendingTableNavigationDetails = null;
        return;
    }
    let formUrl = `/reservieren?table_id=${encodeURIComponent(details.tableId)}`;
    formUrl += `&table_name=${encodeURIComponent(details.tableName)}`;
    formUrl += `&date=${encodeURIComponent(details.selectedDate)}`;
    formUrl += `&shift=${encodeURIComponent(details.selectedShift)}`;
    window.location.href = formUrl;
    pendingTableNavigationDetails = null;
}

function editReservation(reservationId) {
    window.location.href = `/reservierung_bearbeiten/${reservationId}`;
}

function closeOccupiedTableInfoModal() {
    if (occupiedTableInfoModal) {
        occupiedTableInfoModal.classList.remove('active');
    }
}

function closeConfirmAddReservationModal() {
    if (confirmAddResModal) {
        confirmAddResModal.classList.remove('active');
    }
    pendingTableNavigationDetails = null;
}

function deleteReservationPrompt(reservationId, tableName, guestName, reservationDateForDisplay, originalDateForReload) {
    const filterDateInput = document.getElementById('filterDate');
    activeFilterDateBeforeDelete = filterDateInput ? filterDateInput.value : originalDateForReload;
    if (!deleteConfirmationModal || !deleteModalMessageText) {
        if (confirm(`Möchten Sie die Reservierung für ${guestName} am Tisch ${tableName} (${reservationDateForDisplay}) wirklich löschen?`)) {
            performActualDelete(reservationId);
        }
        return;
    }
    currentReservationIdToDelete = reservationId;
    deleteModalMessageText.textContent = `Möchten Sie die Reservierung für ${guestName} am Tisch ${tableName} (${reservationDateForDisplay}) wirklich löschen?`;
    if (deleteConfirmationModal) deleteConfirmationModal.classList.add('active');
}

function performActualDelete(reservationId) {
    if (!reservationId) return;
    const apiUrl = `/api/reservierung_loeschen/${reservationId}`;
    fetch(apiUrl, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => {
        if (!response.ok) { return response.json().catch(() => ({ message: `HTTP Fehler ${response.status}` })).then(errorData => { throw errorData; }); }
        return response.json();
    })
    .then(data => {
        let messageHtml = '';
        if (data.success) {
            messageHtml = `<div class="confirmation-message"><h3>${data.message || 'Erfolgreich gelöscht!'}</h3><p>Die Reservierung wurde entfernt.</p><div class="modal-actions"><button onclick="closeStatusModalAndReload()" class="button">Schließen & Aktualisieren</button></div></div>`;
        } else {
            messageHtml = `<div class="error-message"><h3>Fehler</h3><p>${data.message || 'Löschen fehlgeschlagen.'}</p><div class="modal-actions"><button onclick="closeStatusModal()" class="button">Schließen</button></div></div>`;
        }
        if (deleteStatusModalContent) { deleteStatusModalContent.innerHTML = messageHtml; if (deleteStatusModal) deleteStatusModal.classList.add('active'); }
    })
    .catch(error => {
        const errorMessageText = error.message || "Ein unerwarteter Fehler ist aufgetreten.";
        const messageHtml = `<div class="error-message"><h3>Fehler</h3><p>${errorMessageText}</p><div class="modal-actions"><button onclick="closeStatusModal()" class="button">Schließen</button></div></div>`;
        if (deleteStatusModalContent) { deleteStatusModalContent.innerHTML = messageHtml; if (deleteStatusModal) deleteStatusModal.classList.add('active'); }
    });
    currentReservationIdToDelete = null;
}

function closeStatusModal() {
    if (deleteStatusModal) deleteStatusModal.classList.remove('active');
}

function closeStatusModalAndReload() {
    closeStatusModal();
    let targetUrl = '/reservierungen';
    const currentPath = window.location.pathname;
    if (currentPath === '/' && activeFilterDateBeforeDelete && document.getElementById('shiftPicker')) {
        targetUrl = `/?date=${encodeURIComponent(activeFilterDateBeforeDelete)}`;
        const shiftValue = document.getElementById('shiftPicker').value;
        if (shiftValue) {
            targetUrl += `&shift=${encodeURIComponent(shiftValue)}`;
        }
    } else if (currentPath.includes('/reservierungen') && activeFilterDateBeforeDelete !== null) {
         targetUrl = `/reservierungen?filter_date=${encodeURIComponent(activeFilterDateBeforeDelete)}`;
    }
    window.location.href = targetUrl;
}

function openMoveReservationModal(reservationId, guestName, resDate, resTime, resPersons) {
    if (!moveReservationModal || !moveReservationGuestName || !moveReservationDetails || !availableTablesListDiv) {
        alert('Verschieben-Funktion ist momentan nicht verfügbar.');
        return;
    }
    currentReservationToMoveId = reservationId;
    if(moveReservationGuestName) moveReservationGuestName.textContent = guestName;
    if(moveReservationDetails) moveReservationDetails.textContent = `für ${resPersons} Pers. am ${resDate} um ${resTime}`;
    if(availableTablesListDiv) availableTablesListDiv.innerHTML = '<p>Verfügbare Tische werden geladen...</p>';
    if(moveReservationModal) moveReservationModal.classList.add('active');
    fetch(`/api/available_tables_for_move/${reservationId}`)
        .then(response => {
            if (!response.ok) { return response.json().then(err => { throw new Error(err.message || `Serverfehler: ${response.status}`) }); }
            return response.json();
        })
        .then(data => {
            if (data.success && data.available_tables) { renderAvailableTables(data.available_tables); }
            else { if(availableTablesListDiv) availableTablesListDiv.innerHTML = `<p>${data.message || 'Keine verfügbaren Tische gefunden oder Fehler.'}</p>`; }
        })
        .catch(error => {
            if(availableTablesListDiv) availableTablesListDiv.innerHTML = `<p>Fehler: ${error.message}</p>`;
        });
}

function renderAvailableTables(tables) {
    if (!availableTablesListDiv) return;
    if (tables.length === 0) {
        availableTablesListDiv.innerHTML = '<p>Keine Tische gefunden, auf die diese Reservierung (zur aktuellen Uhrzeit) verschoben werden kann.</p>';
        return;
    }
    availableTablesListDiv.innerHTML = '';
    tables.forEach(table => {
        const tableItem = document.createElement('div');
        tableItem.classList.add('available-table-item');
        let tableText = `${table.display_name}`;
        if (table.existing_reservations_at_other_times && table.existing_reservations_at_other_times.length > 0) {
            tableText += ` <small style="color: #7f8c8d;">(bereits belegt ab: `;
            table.existing_reservations_at_other_times.forEach((res, index) => {
                tableText += `${res.time}${index < table.existing_reservations_at_other_times.length - 1 ? ', ' : ''}`;
            });
            tableText += `)</small>`;
        } else {
            tableText += ` <small style="color: green;">(komplett frei in dieser Schicht)</small>`;
        }
        tableItem.innerHTML = tableText;
        tableItem.setAttribute('data-new-table-id', table.id);
        tableItem.setAttribute('data-table-name', table.display_name);
        tableItem.onclick = function() {
            confirmAndExecuteMove(currentReservationToMoveId, table.id, table.display_name);
        };
        availableTablesListDiv.appendChild(tableItem);
    });
}

function confirmAndExecuteMove(originalReservationId, newTableId, newTableName) {
    if (!confirmMoveActionModal || !confirmMoveActionModalText || !executeMoveBtn || !cancelMoveActionBtn) {
        if (confirm(`Möchten Sie die Reservierung wirklich auf Tisch ${newTableName} verschieben?`)) {
            executeMoveOnServer(originalReservationId, newTableId);
        }
        return;
    }
    pendingMoveDetails = { originalReservationId, newTableId };
    if(confirmMoveActionModalText) confirmMoveActionModalText.textContent = `Möchten Sie die Reservierung wirklich auf Tisch ${newTableName} verschieben?`;
    if(confirmMoveActionModal) confirmMoveActionModal.classList.add('active');
}

function executeMoveOnServer(reservationId, newTableId) {
    fetch(`/api/move_reservation/${reservationId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_table_id: newTableId })
    })
    .then(response => response.json())
    .then(data => {
        closeMoveReservationModal();
        let messageHtml = '';
        if (data.success) {
            messageHtml = `<div class="confirmation-message"><h3>${data.message || "Erfolgreich verschoben!"}</h3><div class="modal-actions"><button onclick="closeStatusModalAndReload()" class="button">Schließen & Aktualisieren</button></div></div>`;
        } else {
            messageHtml = `<div class="error-message"><h3>Fehler</h3><p>${data.message || 'Verschieben fehlgeschlagen.'}</p><div class="modal-actions"><button onclick="closeStatusModal()" class="button">Schließen</button></div></div>`;
        }
        if (deleteStatusModalContent) { deleteStatusModalContent.innerHTML = messageHtml; if (deleteStatusModal) deleteStatusModal.classList.add('active'); }
        else { if (data.success) closeStatusModalAndReload(); }
    })
    .catch(error => {
        alert(`Fehler: ${error.message}`);
        closeMoveReservationModal();
    });
}

function closeMoveReservationModal() {
    if (moveReservationModal) { moveReservationModal.classList.remove('active'); }
    currentReservationToMoveId = null;
    if (availableTablesListDiv) { availableTablesListDiv.innerHTML = '<p>Verfügbare Tische werden geladen...</p>'; }
}

function toggleArrival(reservationId, buttonElement) {
    fetch(`/api/reservierung_angekommen/${reservationId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => {
        if (!response.ok) { return response.json().then(err => { throw new Error(err.message || `Serverfehler`) }); }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            if (data.arrived) {
                buttonElement.textContent = 'Gast da';
                buttonElement.classList.remove('pending-arrival');
                buttonElement.classList.add('arrived');
            } else {
                buttonElement.textContent = 'Angekommen?';
                buttonElement.classList.remove('arrived');
                buttonElement.classList.add('pending-arrival');
            }
            const tableRow = document.querySelector(`tr[data-row-id="${reservationId}"]`);
            if (tableRow) {
                if (data.arrived) { tableRow.classList.add('guest-arrived'); }
                else { tableRow.classList.remove('guest-arrived'); }
            }
        } else {
            alert(`Fehler: ${data.message || 'Status konnte nicht aktualisiert werden.'}`);
        }
    })
    .catch(error => {
        alert(`Fehler: ${error.message}`);
    });
}

function markReservationAsDeparted(reservationId, buttonElement) {
    if (!reservationId) {
        console.error("Keine reservationId für markReservationAsDeparted übergeben.");
        return;
    }
    const apiUrl = `/api/reservierung_gegangen/${encodeURIComponent(reservationId)}`;
    fetch(apiUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => {
                const errorMessage = err.message || `Serverfehler: ${response.status} ${response.statusText}`;
                throw new Error(errorMessage);
            });
        }
        return response.json();
    })
    .then(data => {
        if (data.success && data.departed) {
            const actionsCell = buttonElement.closest('.actions-cell');
            if (actionsCell) {
                const arrivalButton = actionsCell.querySelector('.button-arrival');
                const departedButton = buttonElement;
                if (arrivalButton) {
                    arrivalButton.style.display = 'none';
                }
                if (departedButton) {
                    departedButton.style.display = 'none';
                }
                const statusDepartedButton = document.createElement('button');
                statusDepartedButton.className = 'button button-status-departed';
                statusDepartedButton.textContent = 'Gast gegangen';
                statusDepartedButton.disabled = true;
                actionsCell.appendChild(statusDepartedButton);
                const tableRow = actionsCell.closest('tr');
                if (tableRow) {
                    tableRow.classList.add('guest-departed-row');
                    tableRow.classList.remove('guest-arrived');
                }
            }
        } else {
            alert(`Fehler: ${data.message || 'Status konnte nicht auf "gegangen" gesetzt werden.'}`);
        }
    })
    .catch(error => {
        console.error('Fehler beim Markieren als gegangen:', error);
        alert(`Ein Fehler ist aufgetreten: ${error.message}`);
    });
}

function showModalStatusMessage(message, isSuccess, redirectUrl = null) {

    if (!statusModal || !statusModalContent) {
        console.error("FEHLER: statusModal oder statusModalContent ist NICHT im DOM gefunden!");
        return;
    }

    let messageHtml = `
        <div class="${isSuccess ? 'confirmation-message' : 'error-message'}">
            <h3>${isSuccess ? 'Erfolg!' : 'Fehler!'}</h3>
            <p>${message}</p>
            <div class="modal-actions" style="margin-top:20px; text-align:center;">
                <button id="closeFormStatusModalBtn" class="button">${isSuccess && redirectUrl ? 'Schließen & Weiter' : 'Schließen'}</button>
            </div>
        </div>`;
    statusModalContent.innerHTML = messageHtml;

    statusModal.style.display = 'flex';

    const closeButton = document.getElementById('closeFormStatusModalBtn');
    if (!closeButton) {
        console.error("FEHLER: Der Button 'closeFormStatusModalBtn' wurde im Modal-Inhalt NICHT gefunden!");
        return;
    }

    closeButton.addEventListener('click', function handleCloseAndRedirect() {
        statusModal.style.display = 'none';
        if (isSuccess && redirectUrl) {
            window.location.href = redirectUrl;
        } else {
        }
    }, { once: true });
}

document.addEventListener('DOMContentLoaded', function() {
    const dateInputForIndex = document.getElementById('reservationDate');
    const shiftPickerForIndex = document.getElementById('shiftPicker');

    function reloadIndexPageWithFilters() {
        if (window.location.pathname !== '/') return;
        let url = '/?';
        const params = [];
        if (dateInputForIndex && dateInputForIndex.value) {
            params.push("date=" + dateInputForIndex.value);
        }
        if (shiftPickerForIndex && shiftPickerForIndex.value) {
            params.push("shift=" + shiftPickerForIndex.value);
        }
        window.location.href = url + params.join("&");
    }

    if (dateInputForIndex && window.location.pathname === '/') {
        const today = new Date().toISOString().split('T')[0];
        dateInputForIndex.setAttribute('min', today);
        if (!dateInputForIndex.value && !new URLSearchParams(window.location.search).has('date')) {
        }
        dateInputForIndex.addEventListener('change', reloadIndexPageWithFilters);
    }
    if (shiftPickerForIndex && window.location.pathname === '/') {
        shiftPickerForIndex.addEventListener('change', reloadIndexPageWithFilters);
    }

    const dateTimeDisplayElement = document.getElementById('current-datetime-display');
    function updateLiveDateTime() {
        if (dateTimeDisplayElement) {
            const now = new Date();
            const day = now.getDate().toString().padStart(2, '0');
            const month = (now.getMonth() + 1).toString().padStart(2, '0');
            const year = now.getFullYear();
            const hours = now.getHours().toString().padStart(2, '0');
            const minutes = now.getMinutes().toString().padStart(2, '0');
            const seconds = now.getSeconds().toString().padStart(2, '0');
            dateTimeDisplayElement.innerHTML = `${day}.${month}.${year}<br>${hours}:${minutes}:${seconds}`;
        }
    }
    if (dateTimeDisplayElement) {
        updateLiveDateTime();
        setInterval(updateLiveDateTime, 1000);
    }

    if (cancelDeleteBtn) {
        cancelDeleteBtn.addEventListener('click', function() {
            if (deleteConfirmationModal) deleteConfirmationModal.classList.remove('active');
            currentReservationIdToDelete = null;
        });
    }
    if (confirmDeleteBtn) {
        confirmDeleteBtn.addEventListener('click', function() {
            if (deleteConfirmationModal) deleteConfirmationModal.classList.remove('active');
            if (currentReservationIdToDelete) {
                performActualDelete(currentReservationIdToDelete);
            }
        });
    }

    if (executeMoveBtn) {
        executeMoveBtn.addEventListener('click', function() {
            if (pendingMoveDetails) {
                executeMoveOnServer(pendingMoveDetails.originalReservationId, pendingMoveDetails.newTableId);
            }
            if (confirmMoveActionModal) confirmMoveActionModal.classList.remove('active');
            pendingMoveDetails = null;
        });
    }
    if (cancelMoveActionBtn) {
        cancelMoveActionBtn.addEventListener('click', function() {
            if (confirmMoveActionModal) confirmMoveActionModal.classList.remove('active');
            pendingMoveDetails = null;
        });
    }

    if (proceedWithReservationBtn) {
        proceedWithReservationBtn.addEventListener('click', function() {
            const detailsToNavigate = pendingTableNavigationDetails;
            closeConfirmAddReservationModal();
            navigateToReservationForm(detailsToNavigate);
        });
    }
    if (cancelAddReservationBtn) {
        cancelAddReservationBtn.addEventListener('click', closeConfirmAddReservationModal);
    }

    const allModalsForGenericClose = [
        occupiedTableInfoModal,
        deleteConfirmationModal,
        deleteStatusModal,
        moveReservationModal,
        confirmMoveActionModal,
        confirmAddResModal
    ];

    allModalsForGenericClose.forEach(modal => {
        if (modal) {
            if (modal.classList.contains('modal-overlay')) {
                modal.addEventListener('click', function(event) {
                    if (event.target === modal) {
                        if (modal === confirmAddResModal) {
                            closeConfirmAddReservationModal();
                        } else if (modal === deleteConfirmationModal) {
                            if (deleteConfirmationModal) deleteConfirmationModal.classList.remove('active');
                            currentReservationIdToDelete = null;
                        } else if (modal === moveReservationModal) {
                            closeMoveReservationModal();
                        } else if (modal === confirmMoveActionModal) {
                            if (confirmMoveActionModal) confirmMoveActionModal.classList.remove('active');
                            pendingMoveDetails = null;
                        } else if (modal === occupiedTableInfoModal) {
                            closeOccupiedTableInfoModal();
                        } else {
                             modal.classList.remove('active');
                        }
                    }
                });
            }
            const closeButton = modal.querySelector('.modal-close-button');
            if (closeButton && !closeButton.hasAttribute('onclick')) {
                closeButton.addEventListener('click', function() {
                    if (modal === confirmAddResModal) {
                        closeConfirmAddReservationModal();
                    } else if (modal === deleteConfirmationModal) {
                        if (deleteConfirmationModal) deleteConfirmationModal.classList.remove('active');
                        currentReservationIdToDelete = null;
                    } else if (modal === moveReservationModal) {
                        closeMoveReservationModal();
                    } else if (modal === confirmMoveActionModal) {
                        if (confirmMoveActionModal) confirmMoveActionModal.classList.remove('active');
                        pendingMoveDetails = null;
                    } else if (modal === occupiedTableInfoModal) {
                        closeOccupiedTableInfoModal();
                    } else {
                        modal.classList.remove('active');
                    }
                });
            }
        }
    });
});
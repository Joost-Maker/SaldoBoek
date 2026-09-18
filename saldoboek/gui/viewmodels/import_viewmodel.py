"""ImportViewModel - ViewModel voor transactie import."""

import logging
from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot

logger = logging.getLogger(__name__)


class ImportViewModel(QObject):
    """
    ViewModel voor het importeren van transacties.

    Verantwoordelijk voor:
    - Selecteren van bestanden
    - Starten van import via service
    - Bijhouden van import voortgang
    - Resultaten tonen

    Signal/slot communicatie met de View.
    """

    # Signals voor communicatie met View
    import_started = Signal()
    import_progress = Signal(str)  # Status bericht
    import_finished = Signal(int, list)  # aantal, ongecategoriseerd
    import_error = Signal(str)  # Error bericht
    files_changed = Signal(list)  # Lijst van geselecteerde bestanden

    def __init__(self, transaction_service, parent=None):
        """
        Initialiseer ImportViewModel.

        Args:
            transaction_service: TransactionService instantie
            parent: Parent QObject
        """
        super().__init__(parent)
        self._service = transaction_service
        self._gebruiker_id = None
        self._selected_files = []
        self._bank_type = "auto"  # auto, rabobank, sns, knab
        self._account_type = "betaalrekening"  # betaalrekening, spaarrekening

    def set_gebruiker_id(self, gebruiker_id: int) -> None:
        """Stel de gebruiker ID in."""
        self._gebruiker_id = gebruiker_id

    def set_bank_type(self, bank_type: str) -> None:
        """
        Stel het bank type in.

        Args:
            bank_type: 'auto', 'rabobank', of 'sns'
        """
        self._bank_type = bank_type

    def get_selected_files(self) -> list:
        """Geef de geselecteerde bestanden terug."""
        return self._selected_files.copy()

    def set_selected_files(self, files: list) -> None:
        """
        Stel de geselecteerde bestanden in.

        Args:
            files: Lijst van bestandspaden
        """
        self._selected_files = files
        self.files_changed.emit(self._selected_files)

    def add_files(self, files: list) -> None:
        """
        Voeg bestanden toe aan de selectie.

        Args:
            files: Lijst van bestandspaden om toe te voegen
        """
        for f in files:
            if f not in self._selected_files:
                self._selected_files.append(f)
        self.files_changed.emit(self._selected_files)

    def clear_files(self) -> None:
        """Wis alle geselecteerde bestanden."""
        self._selected_files = []
        self.files_changed.emit(self._selected_files)

    def has_files(self) -> bool:
        """Check of er bestanden geselecteerd zijn."""
        return len(self._selected_files) > 0

    def get_file_count(self) -> int:
        """Geef het aantal geselecteerde bestanden."""
        return len(self._selected_files)

    def start_import(self) -> None:
        """Start de import van geselecteerde bestanden."""
        if not self._selected_files:
            self.import_error.emit("Geen bestanden geselecteerd")
            return

        if not self._service or not self._gebruiker_id:
            self.import_error.emit("Geen service of gebruiker ingesteld")
            return

        self.import_started.emit()
        self.import_progress.emit("Start met importeren...")

        try:
            resultaat = self._service.import_files(
                self._selected_files, self._gebruiker_id, self._account_type
            )

            if isinstance(resultaat, tuple):
                totaal, ongecategoriseerd = resultaat
                self.import_finished.emit(totaal, ongecategoriseerd)
            else:
                self.import_finished.emit(resultaat, [])

        except Exception as e:
            logger.error("Import fout: %s", str(e))
            self.import_error.emit(str(e))

    @Slot(str)
    def on_file_selected(self, file_path: str) -> None:
        """
        Handle een nieuw geselecteerd bestand.

        Args:
            file_path: Pad naar het bestand
        """
        if file_path and file_path not in self._selected_files:
            self._selected_files.append(file_path)
            self.files_changed.emit(self._selected_files)

    @Slot()
    def on_import_completed(self) -> None:
        """Reset de view nach import voltooiing."""
        self._selected_files = []
        self.files_changed.emit(self._selected_files)

    def get_file_names(self) -> list:
        """
        Geef alleen de bestandsnamen (zonder pad).

        Returns:
            Lijst van bestandsnamen
        """
        import os

        return [os.path.basename(f) for f in self._selected_files]

    def set_account_type(self, account_type: str) -> None:
        """
        Stel het account type in (betaalrekening of spaarrekening).

        Args:
            account_type: 'betaalrekening' of 'spaarrekening'
        """
        self._account_type = account_type

    def get_account_type(self) -> str:
        """Geef het ingestelde account type terug."""
        return self._account_type

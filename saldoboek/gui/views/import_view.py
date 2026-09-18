"""ImportView - Importeer transacties uit CSV bestanden."""

import logging
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class ImportView(QWidget):
    """
    View voor het importeren van transacties.

    Deze view ontvangt data via de ViewModel en stuurt gebruikersacties
    door naar de ViewModel. Alle business logic zit in ImportViewModel.
    """

    # Signal doorgegeven aan MainWindow voor refresh
    import_completed = Signal(int)

    def __init__(self, viewmodel, parent=None):
        """
        Initialiseer ImportView.

        Args:
            viewmodel: ImportViewModel instantie
            parent: Parent widget
        """
        super().__init__(parent)
        self._viewmodel = viewmodel
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Bouwt de UI op."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header
        header = QFrame()
        header_layout = QHBoxLayout(header)

        title = QLabel("Transacties Importeren")
        title.setObjectName("view_title")
        header_layout.addWidget(title)
        header_layout.addStretch()

        layout.addWidget(header)

        # File selection area
        file_frame = QFrame()
        file_frame.setObjectName("file_frame")
        file_layout = QVBoxLayout(file_frame)

        # Bank type dropdown (for display only, actual parsing auto-detects)
        bank_layout = QHBoxLayout()
        bank_label = QLabel("Bank type:")
        bank_layout.addWidget(bank_label)
        self._bank_combo = QComboBox()
        self._bank_combo.setObjectName("bank_combo")
        self._bank_combo.addItems(["Auto-detecteren", "Rabobank", "SNS Bank", "Knab"])
        bank_layout.addWidget(self._bank_combo)
        bank_layout.addStretch()
        file_layout.addLayout(bank_layout)

        # Account type selection for SNS/other banks
        account_layout = QHBoxLayout()
        account_label = QLabel("Rekeningtype:")
        account_layout.addWidget(account_label)

        self._account_type_group = QButtonGroup()
        self._betaal_radio = QRadioButton("Betaalrekening")
        self._betaal_radio.setObjectName("betaal_radio")
        self._betaal_radio.setChecked(True)
        self._account_type_group.addButton(self._betaal_radio, 1)
        account_layout.addWidget(self._betaal_radio)

        self._spaar_radio = QRadioButton("Spaarrekening")
        self._spaar_radio.setObjectName("spaar_radio")
        self._account_type_group.addButton(self._spaar_radio, 2)
        account_layout.addWidget(self._spaar_radio)

        account_layout.addStretch()
        file_layout.addLayout(account_layout)

        # Selected files list
        self._files_label = QLabel("Geen bestanden geselecteerd")
        self._files_label.setObjectName("files_label")
        self._files_label.setWordWrap(True)
        file_layout.addWidget(self._files_label)

        # Buttons
        btn_layout = QHBoxLayout()
        self._select_btn = QPushButton("📂 Bestanden Selecteren")
        self._select_btn.setObjectName("select_button")
        self._select_btn.clicked.connect(self._on_select_clicked)
        btn_layout.addWidget(self._select_btn)

        self._clear_btn = QPushButton("🗑️ Wissen")
        self._clear_btn.setObjectName("clear_button")
        self._clear_btn.clicked.connect(self._on_clear_clicked)
        self._clear_btn.setEnabled(False)
        btn_layout.addWidget(self._clear_btn)

        btn_layout.addStretch()
        file_layout.addLayout(btn_layout)

        layout.addWidget(file_frame)

        # Import button
        self._import_btn = QPushButton("▶️ Importeren")
        self._import_btn.setObjectName("import_button")
        self._import_btn.clicked.connect(self._on_import_clicked)
        self._import_btn.setEnabled(False)
        layout.addWidget(self._import_btn)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setObjectName("progress_bar")
        self._progress_bar.setVisible(False)
        self._progress_bar.setMinimumWidth(400)
        layout.addWidget(self._progress_bar)

        # Status label
        self._status_label = QLabel("")
        self._status_label.setObjectName("status_label")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        # Result table for uncategorized
        result_frame = QFrame()
        result_frame.setObjectName("result_frame")
        result_layout = QVBoxLayout(result_frame)

        result_title = QLabel("Importeer Resultaat")
        result_title.setObjectName("result_title")
        result_layout.addWidget(result_title)

        self._result_table = QTableWidget()
        self._result_table.setObjectName("result_table")
        self._result_table.setColumnCount(4)
        self._result_table.setHorizontalHeaderLabels(
            ["Datum", "Naam", "Omschrijving", "Bedrag"]
        )
        self._result_table.setMaximumHeight(200)
        self._result_table.setVisible(False)
        # Enable column resizing by user
        header = self._result_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        self._result_table.setColumnWidth(0, 100)  # Datum
        self._result_table.setColumnWidth(1, 150)  # Naam
        self._result_table.setColumnWidth(2, 250)  # Omschrijving
        self._result_table.setColumnWidth(3, 100)  # Bedrag
        result_layout.addWidget(self._result_table)

        layout.addWidget(result_frame)

        layout.addStretch()

    def _connect_signals(self):
        """Verbind signals van de ViewModel met slots in de View."""
        self._viewmodel.import_started.connect(self._on_import_started)
        self._viewmodel.import_progress.connect(self._on_import_progress)
        self._viewmodel.import_finished.connect(self._on_import_finished)
        self._viewmodel.import_error.connect(self._on_import_error)
        self._viewmodel.files_changed.connect(self._on_files_changed)

    # ViewModel signal handlers

    def _on_import_started(self):
        """Handle import gestart van ViewModel."""
        self._import_btn.setEnabled(False)
        self._select_btn.setEnabled(False)
        self._clear_btn.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setRange(0, 0)
        self._status_label.setText("Importeren...")
        self._result_table.setVisible(False)

    def _on_import_progress(self, bericht):
        """Handle import voortgang van ViewModel."""
        self._status_label.setText(bericht)

    def _on_import_finished(self, aantal, ongecategoriseerd):
        """Handle import voltooid van ViewModel."""
        self._progress_bar.setVisible(False)
        self._import_btn.setEnabled(True)
        self._select_btn.setEnabled(True)

        if aantal > 0:
            self._status_label.setText(
                f"✓ {aantal} transacties succesvol geïmporteerd!"
            )
        else:
            self._status_label.setText(
                "Geen nieuwe transacties gevonden (mogelijk duplicaten)."
            )

        if ongecategoriseerd:
            self._status_label.setText(
                self._status_label.text()
                + f"\n{len(ongecategoriseerd)} transacties vereisen handmatige categorisatie."
            )
            self._toon_ongecategoriseerd(ongecategoriseerd)

        # Emit signaal voor MainWindow om transacties te refreshen
        self.import_completed.emit(aantal)

    def _on_import_error(self, fout_bericht):
        """Handle import error van ViewModel."""
        self._progress_bar.setVisible(False)
        self._import_btn.setEnabled(True)
        self._select_btn.setEnabled(True)
        self._status_label.setText(f"Fout bij importeren: {fout_bericht}")

    def _on_files_changed(self, files):
        """Handle geselecteerde bestanden gewijzigd."""
        if files:
            self._files_label.setText(
                f"{len(files)} bestand(en) geselecteerd:\n"
                + "\n".join(os.path.basename(f) for f in files)
            )
            self._import_btn.setEnabled(True)
            self._clear_btn.setEnabled(True)
        else:
            self._files_label.setText("Geen bestanden geselecteerd")
            self._import_btn.setEnabled(False)
            self._clear_btn.setEnabled(False)

    # User action handlers (forward to ViewModel)

    def _on_select_clicked(self):
        """Open file dialog om bestanden te selecteren."""
        bestanden, _ = QFileDialog.getOpenFileNames(
            self,
            "Selecteer transactie bestanden",
            "",
            "CSV Files (*.csv);;Alle Bestanden (*.*)",
        )

        if bestanden:
            self._viewmodel.set_selected_files(bestanden)

    def _on_clear_clicked(self):
        """Wis de geselecteerde bestanden via ViewModel."""
        self._viewmodel.clear_files()

    def _on_import_clicked(self):
        """Start de import via ViewModel."""
        # Set account type based on radio button selection
        if self._account_type_group.checkedId() == 1:
            self._viewmodel.set_account_type("betaalrekening")
        else:
            self._viewmodel.set_account_type("spaarrekening")

        self._viewmodel.start_import()

    # Rendering helpers

    def _toon_ongecategoriseerd(self, items):
        """Toon ongecategoriseerde transacties in de result table."""
        self._result_table.setRowCount(len(items))
        self._result_table.setVisible(True)

        for row, item in enumerate(items):
            self._result_table.setItem(
                row, 0, QTableWidgetItem(str(item.get("datum", "")))
            )
            self._result_table.setItem(
                row, 1, QTableWidgetItem(str(item.get("naam", "")))
            )
            self._result_table.setItem(
                row, 2, QTableWidgetItem(str(item.get("omschrijving", "")))
            )

            bedrag = item.get("bedrag", 0)
            bedrag_item = QTableWidgetItem(f"€{bedrag:,.2f}")
            if bedrag < 0:
                bedrag_item.setForeground(Qt.red)
            else:
                bedrag_item.setForeground(Qt.darkGreen)
            self._result_table.setItem(row, 3, bedrag_item)

    # Public methods

    def set_gebruiker_id(self, gebruiker_id):
        """Stel de gebruiker ID in via ViewModel."""
        self._viewmodel.set_gebruiker_id(gebruiker_id)

    def reset(self):
        """Reset de view naar beginstaat."""
        self._viewmodel.clear_files()
        self._status_label.setText("")
        self._progress_bar.setVisible(False)
        self._result_table.setVisible(False)
        self._result_table.setRowCount(0)

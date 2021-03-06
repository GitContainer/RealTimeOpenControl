#!/usr/bin/python3
# -*- coding:utf-8 -*-

# Source: https://python-forum.io/Thread-Read-Write-CSV-Qt5

import csv
import codecs
import os
from io import StringIO
import sys
from PyQt5 import QtCore, QtGui, QtWidgets, QtPrintSupport
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import QFile
import pandas as pd
import traceback
import scipy.io as sio
import ezodf

from PyQt5 import uic
import re

try:
    from .data.lib import general_lib as lib
    from .data.lib import pyqt_customlib as pyqtlib
    from .data import csvSignalWidget
except ImportError:
    from data.lib import general_lib as lib
    from data.lib import pyqt_customlib as pyqtlib
    from data import csvSignalWidget


translate = QCoreApplication.translate


class RTOC_Import(QtWidgets.QMainWindow):
    def __init__(self, fileName='', parent=None, sendSignals=None):
        super(RTOC_Import, self).__init__(parent)
        if getattr(sys, 'frozen', False):
            # frozen
            packagedir = os.path.dirname(sys.executable)
        else:
            # unfrozen
            packagedir = os.path.dirname(os.path.realpath(__file__))
        uic.loadUi(packagedir+"/data/ui/csveditor.ui", self)

        self.self = parent
        if parent:
            self.config = parent.config
        self.sendSignals=sendSignals

        self.fileName = ""
        self.path = ''
        self.fname = "Liste"
        self.model = QtGui.QStandardItemModel(self)

        self.tableView.setModel(self.model)

        self.connectGUI()

        self.signals = []
        if parent:
            self.profiles= self.config['csv_profiles']
            self.loadProfiles()
        else:
            self.profiles= {}

        item = QtGui.QStandardItem()
        self.model.appendRow(item)
        self.model.setData(self.model.index(0, 0), "", 0)
        self.tableView.resizeColumnsToContents()

        self.tableView.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tableView.customContextMenuRequested.connect(self.contextMenuEventCSV)

        self.signalListWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.signalListWidget.customContextMenuRequested.connect(self.contextMenuEventSignals)

        if fileName != '':
            self.loadCsv(fileName)

    def connectGUI(self):
        self.model.dataChanged.connect(self.finishedEdit)
        self.pushButtonLoad.triggered.connect(self.loadCsvAction)
        self.pushButtonWrite.triggered.connect(self.writeCsv)
        self.pushButtonPreview.triggered.connect(self.handlePreview)
        self.pushButtonPrint.triggered.connect(self.handlePrint)
        self.pushClear.triggered.connect(self.clearList)

        self.pushAddRow.clicked.connect(self.addRow)
        self.pushDeleteRow.clicked.connect(self.removeRow)
        self.pushAddColumn.clicked.connect(self.addColumn)
        self.pushDeleteColumn.clicked.connect(self.removeColumn)

        self.pushSwapXY.clicked.connect(self.swapXY)
        self.columnDivComboBox.currentTextChanged.connect(self.divisorsChanged)
        self.rowDivComboBox.currentTextChanged.connect(self.divisorsChanged)
        self.rowDivComboBox.hide()
        self.label_4.hide()
        self.loadProfileButton.clicked.connect(self.loadProfile)
        self.addProfileButton.clicked.connect(self.addProfile)
        self.removeProfileButton.clicked.connect(self.removeProfile)

        self.signalListWidget.currentTextChanged.connect(self.addNewSignal)

        self.importButton.clicked.connect(self.importToLogger)

    def getRow(self, row):
        if row < self.model.rowCount():
            rowItems = [self.model.item(row, column) for column in range(self.model.columnCount())]
        else:
            rowItems = None
        return rowItems

    def getColumn(self, column):
        if column < self.model.columnCount():
            columnItems = [self.model.item(row,column) for row in range(self.model.rowCount())]
        else:
            columnItems = None
        return columnItems

    def loadCsvAction(self):
        fileName, _ = QtWidgets.QFileDialog.getOpenFileName(self, translate('csveditor', "CSV-Datei öffnen"),
                                                            (QtCore.QDir.homePath()), "Tabelle (*.csv *.tsv, *.xls, *.xlsx, *.txt, *.mat, *)")
        if fileName:
            self.loadCsv(fileName)

    def loadCsv(self, fileName, manualDelimiter = False):
        self.path=fileName
        try:
            ff = open(fileName, 'r')
            mytext = ff.read()
    #            print(mytext)
            ff.close()
            self.loadCsvStr(mytext, manualDelimiter)
        except:
            try:
                try:
                    xl = pd.ExcelFile(fileName)
                    # Print the sheet names
                    print(xl.sheet_names)
                    # Load a sheet into a DataFrame by name: df1
                    df1 = xl.parse(xl.sheet_names[0])
                except:
                    doc = ezodf.opendoc(fileName)

                    print("Spreadsheet contains %d sheet(s)." % len(doc.sheets))
                    for sheet in doc.sheets:
                        print("-"*40)
                        print("   Sheet name : '%s'" % sheet.name)
                        print("Size of Sheet : (rows=%d, cols=%d)" % (sheet.nrows(), sheet.ncols()) )

                    # convert the first sheet to a pandas.DataFrame
                    sheet = doc.sheets[0]
                    df_dict = {}
                    for i, row in enumerate(sheet.rows()):
                        # row is a list of cells
                        # assume the header is on the first row
                        if i == 0:
                            # columns as lists in a dictionary
                            df_dict = {cell.value:[] for cell in row}
                            # create index for the column headers
                            col_index = {j:cell.value for j, cell in enumerate(row)}
                            continue
                        for j, cell in enumerate(row):
                            # use header instead of column index
                            df_dict[col_index[j]].append(cell.value)
                    # and convert to a DataFrame
                    df1 = pd.DataFrame(df_dict)
                mytext = df1.to_csv(sep='\t')
                self.loadCsvStr(mytext)
            except:
                try:
                    matlabfile = sio.loadmat(fileName)
                    data = []
                    print(matlabfile)
                    for k in matlabfile.keys():
                        if k not in ['__version__','__header__','__globals__']:
                            data.append(k)
                    item, ok = pyqtlib.item_message(self, translate('csveditor','Matlab Import'), translate('csveditor','Bitte wähle einen Datensatz aus der Datei aus.')+'\n'+ matlabfile['__header__'].decode('utf8'), data)
                    if ok:
                        self.path=os.path.splitext(str(self.path))[0].split("/")[-1]+".csv"
                        with open(self.path, 'w', newline='') as myfile:
                            wr = csv.writer(myfile, quoting=csv.QUOTE_ALL)
                            for idx, sig in enumerate(matlabfile[item]):
                                wr.writerow(sig)
                            ff = open(self.path, 'r')
                            mytext = ff.read()
                            ff.close()
                            self.loadCsvStr(mytext)
                except:
                    tb = traceback.format_exc()
                    print(tb)
                    pyqtlib.info_message(translate('csveditor', "Fehler"), translate('csveditor', "Datei ")+fileName+translate('csveditor', " konnte nicht geöffnet werden."), translate('csveditor', "Die Datei ist möglicherweise beschädigt."))

    def loadCsvStr(self, mytext, manualDelimiter=False):
        self.csvInfoLabel.setText(translate('csveditor',''))
        #f = open(fileName, 'r')
        f=StringIO(mytext)
        self.fname = os.path.splitext(str(self.path))[0].split("/")[-1]
        self.setWindowTitle(self.fname)
        if not manualDelimiter:
            try:
                semicolon = mytext.count(';')
                tabs = mytext.count('\t')
                spaces = mytext.count(' ')
                if tabs == 0 and semicolon == 0:
                    print('processing CSV with " "-Delimiter')
                    #f=StringIO(' '.join(mytext.split()))
                    f = StringIO(re.sub(' +', ' ', mytext).strip())
                    #print(re.sub(' +', ' ', mytext).strip())
                    reader = csv.reader(f, delimiter=' ')
                    #reader = pd.read_csv(f, sep=' ')
                elif semicolon <=tabs:
                    #reader = csv.reader(f, delimiter='\t')
                    reader = pd.read_csv(f, sep='\t')
                else:
                    #reader = csv.reader(f, delimiter=';')
                    reader = pd.read_csv(f, sep=';')

                self.model.clear()
                for row in reader:
                    items = []
                    for field in row:
                        if field not in [" ",""]:
                            items.append(QtGui.QStandardItem(field))
                    #items = [QtGui.QStandardItem(field) for field in row]
                    self.model.appendRow(items)
                self.tableView.resizeColumnsToContents()
            except:
                tb = traceback.format_exc()
                print(tb)
                self.csvInfoLabel.setText(translate('csveditor','Fehler in CSV-Datei ->'))
                pyqtlib.info_message(translate('csveditor', "Fehler"), translate('csveditor', "Datei ")+self.fname+translate('csveditor', " konnte nicht gelesen werden."), translate('csveditor', "Stellen Sie sicher, dass die CSV-Datei korrekt ist und die Trennzeichen korrekt sind"))
        else:
            try:
                if self.columnDivComboBox.currentText()==' ':
                    #f=StringIO(' '.join(mytext.split()))
                    f = StringIO(re.sub(' +', ' ', mytext).strip())
                #reader = csv.reader(f, delimiter=self.columnDivComboBox.currentText())
                reader = pd.read_csv(f, sep=self.columnDivComboBox.currentText())
                self.model.clear()
                for row in reader:
                    items = []
                    for field in row:
                        if field not in [" ",""]:
                            items.append(QtGui.QStandardItem(field))
                    #items = [QtGui.QStandardItem(field) for field in row]
                    self.model.appendRow(items)
                self.tableView.resizeColumnsToContents()
            except:
                self.csvInfoLabel.setText(translate('csveditor','Fehler in CSV-Datei ->'))
                pyqtlib.info_message(translate('csveditor', "Fehler"), translate('csveditor', "Datei ")+self.fname+translate('csveditor', " konnte nicht gelesen werden."), translate('csveditor', "Stellen Sie sicher, dass die CSV-Datei korrekt ist und die Trennzeichen korrekt sind"))

    def writeCsv(self, fileName):
        # find empty cells
        for row in range(self.model.rowCount()):
            for column in range(self.model.columnCount()):
                myitem = self.model.item(row, column)
                if myitem is None:
                    item = QtGui.QStandardItem("")
                    self.model.setItem(row, column, item)
        fileName, _ = QtWidgets.QFileDialog.getSaveFileName(self, translate('csveditor', "CSV-Datei speichern"),
                                                            (QtCore.QDir.homePath() + "/" + self.fname + ".csv"), "CSV Files (*.csv)")
        if fileName:
            print(fileName)
            f = open(fileName, 'w')
            with f:
                writer = csv.writer(f, delimiter='\t')
                for rowNumber in range(self.model.rowCount()):
                    fields = [self.model.data(self.model.index(rowNumber, columnNumber),
                                              QtCore.Qt.DisplayRole)
                              for columnNumber in range(self.model.columnCount())]
                    writer.writerow(fields)
                self.fname = os.path.splitext(str(fileName))[0].split("/")[-1]
                self.setWindowTitle(self.fname)

    def handlePrint(self):
        dialog = QtPrintSupport.QPrintDialog()
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.handlePaintRequest(dialog.printer())

    def handlePreview(self):
        dialog = QtPrintSupport.QPrintPreviewDialog()
        dialog.setFixedSize(1000, 700)
        dialog.paintRequested.connect(self.handlePaintRequest)
        dialog.exec_()

    def handlePaintRequest(self, printer):
        # find empty cells
        for row in range(self.model.rowCount()):
            for column in range(self.model.columnCount()):
                myitem = self.model.item(row, column)
                if myitem is None:
                    item = QtGui.QStandardItem("")
                    self.model.setItem(row, column, item)
        printer.setDocName(self.fname)
        document = QtGui.QTextDocument()
        cursor = QtGui.QTextCursor(document)
        model = self.tableView.model()
        table = cursor.insertTable(model.rowCount(), model.columnCount())
        for row in range(table.rows()):
            for column in range(table.columns()):
                cursor.insertText(model.item(row, column).text())
                cursor.movePosition(QtGui.QTextCursor.NextCell)
        document.print_(printer)

    def removeRow(self):
        model = self.model
        indices = self.tableView.selectionModel().selectedRows()
        for index in sorted(indices):
            model.removeRow(index.row())

    def addRow(self):
        item = QtGui.QStandardItem("")
        self.model.appendRow(item)

    def clearList(self):
        self.model.clear()
        self.path = ''

    def removeColumn(self):
        model = self.model
        indices = self.tableView.selectionModel().selectedColumns()
        for index in sorted(indices):
            model.removeColumn(index.column())

    def addColumn(self):
        count = self.model.columnCount()
        self.model.setColumnCount(count + 1)
        self.model.setData(self.model.index(0, count), "", 0)
        self.tableView.resizeColumnsToContents()

    def finishedEdit(self):
        self.tableView.resizeColumnsToContents()
        self.validateSignals()

    def contextMenuEventCSV(self, event):
        self.menu = QtWidgets.QMenu(self)
        # copy
        copyAction = QtWidgets.QAction(translate('csveditor', 'Kopieren'), self)
        copyAction.triggered.connect(lambda: self.copyByContext(event))
        # paste
        pasteAction = QtWidgets.QAction(translate('csveditor', 'Einfügen'), self)
        pasteAction.triggered.connect(lambda: self.pasteByContext(event))
        # cut
        cutAction = QtWidgets.QAction(translate('csveditor', 'Ausschneiden'), self)
        cutAction.triggered.connect(lambda: self.cutByContext(event))
        # delete selected Row
        removeAction = QtWidgets.QAction(translate('csveditor', 'Reihe entfernen'), self)
        removeAction.triggered.connect(lambda: self.deleteRowByContext(event))
        # add Row after
        addAction = QtWidgets.QAction(translate('csveditor', 'Reihe einfügen danach'), self)
        addAction.triggered.connect(lambda: self.addRowByContext(event))
        # add Row before
        addAction2 = QtWidgets.QAction(translate('csveditor', 'Reihe einfügen davor'), self)
        addAction2.triggered.connect(lambda: self.addRowByContext2(event))
        # add Column before
        addColumnBeforeAction = QtWidgets.QAction(
            translate('csveditor', 'Spalte einfügen davor'), self)
        addColumnBeforeAction.triggered.connect(lambda: self.addColumnBeforeByContext(event))
        # add Column after
        addColumnAfterAction = QtWidgets.QAction(
            translate('csveditor', 'Spalte einfügen danach'), self)
        addColumnAfterAction.triggered.connect(lambda: self.addColumnAfterByContext(event))
        # delete Column
        deleteColumnAction = QtWidgets.QAction(translate('csveditor', 'Spalte löschen'), self)
        deleteColumnAction.triggered.connect(lambda: self.deleteColumnByContext(event))
        # add other required actions
        self.menu.addAction(copyAction)
        self.menu.addAction(pasteAction)
        self.menu.addAction(cutAction)
        self.menu.addSeparator()
        self.menu.addAction(addAction)
        self.menu.addAction(addAction2)
        self.menu.addSeparator()
        self.menu.addAction(addColumnBeforeAction)
        self.menu.addAction(addColumnAfterAction)
        self.menu.addSeparator()
        self.menu.addAction(removeAction)
        self.menu.addAction(deleteColumnAction)
        self.menu.popup(QtGui.QCursor.pos())

    def contextMenuEventSignals(self, event):
        self.menu = QtWidgets.QMenu(self)
        # copy
        deleteAction = QtWidgets.QAction(translate('csveditor', 'Signal entfernen'), self)
        deleteAction.triggered.connect(self.removeCurrentSignal)

        self.menu.addAction(deleteAction)
        self.menu.popup(QtGui.QCursor.pos())

    def deleteRowByContext(self, event):
        for i in self.tableView.selectionModel().selection().indexes():
            row = i.row()
            self.model.removeRow(row)
            print("Row " + str(row) + " deleted")
            self.tableView.selectRow(row)

    def addRowByContext(self, event):
        for i in self.tableView.selectionModel().selection().indexes():
            row = i.row() + 1
            self.model.insertRow(row)
            print("Row at " + str(row) + " inserted")
            self.tableView.selectRow(row)

    def addRowByContext2(self, event):
        for i in self.tableView.selectionModel().selection().indexes():
            row = i.row()
            self.model.insertRow(row)
            print("Row at " + str(row) + " inserted")
            self.tableView.selectRow(row)

    def addColumnBeforeByContext(self, event):
        for i in self.tableView.selectionModel().selection().indexes():
            col = i.column()
            self.model.insertColumn(col)
            print("Column at " + str(col) + " inserted")

    def addColumnAfterByContext(self, event):
        for i in self.tableView.selectionModel().selection().indexes():
            col = i.column() + 1
            self.model.insertColumn(col)
            print("Column at " + str(col) + " inserted")

    def deleteColumnByContext(self, event):
        for i in self.tableView.selectionModel().selection().indexes():
            col = i.column()
            self.model.removeColumn(col)
            print("Column at " + str(col) + " removed")

    def copyByContext(self, event):
        for i in self.tableView.selectionModel().selection().indexes():
            row = i.row()
            col = i.column()
            myitem = self.model.item(row, col)
            if myitem is not None:
                clip = QtWidgets.QApplication.clipboard()
                clip.setText(myitem.text())

    def pasteByContext(self, event):
        for i in self.tableView.selectionModel().selection().indexes():
            row = i.row()
            col = i.column()
            myitem = self.model.item(row, col)
            clip = QtWidgets.QApplication.clipboard()
            myitem.setText(clip.text())

    def cutByContext(self, event):
        for i in self.tableView.selectionModel().selection().indexes():
            row = i.row()
            col = i.column()
            myitem = self.model.item(row, col)
            if myitem is not None:
                clip = QtWidgets.QApplication.clipboard()
                clip.setText(myitem.text())
                myitem.setText("")

    def swapXY(self):
        newmodel = QtGui.QStandardItemModel(self)
        for i in reversed(range(self.model.columnCount())):
            c = self.model.takeColumn(i)
            newmodel.insertRow(newmodel.rowCount(), c)
        self.model = newmodel
        self.tableView.setModel(self.model)
        self.tableView.resizeColumnsToContents()
        self.validateSignals()

    def divisorsChanged(self):
        self.loadCsv(self.path, True)

    def loadProfiles(self):
        self.profileComboBox.clear()
        for profile in self.profiles.keys():
            self.profileComboBox.addItem(profile)

    def loadProfile(self):
        if self.profileComboBox.currentText() in self.profiles.keys():
            ok = pyqtlib.alert_message(translate('csveditor', 'Profil laden'), translate('csveditor', 'Wollen Sie das Profil ')+self.profileComboBox.currentText()+translate('csveditor', ' wirklich laden?'), translate('csveditor',"Dabei geht die aktuelle Konfiguration verloren."), "", translate('csveditor', "Ja"), translate('csveditor', "Nein"))
            if ok:
                self.clearSignals()
                profile = self.profiles[self.profileComboBox.currentText()]
                print(profile)
                for p in profile:
                    self.addSignal(p)
                self.updateSignalNames()

    def addProfile(self):
        idx =len(self.profiles)
        text, ok = pyqtlib.text_message(self, translate('csveditor', "Profil speichern"), translate('csveditor', "Speichere die aktuelle Einstellung als Profil\nBitte geben Sie einen Profilnamen an"), translate('csveditor', "Profil ")+str(idx))
        if ok:
            profile = []
            for s in self.signals:
                profile.append(s.read())
            self.profiles[text]=profile
            self.loadProfiles()

    def removeProfile(self):
        ok = pyqtlib.alert_message(translate('csveditor', 'Profil löschen'), translate('csveditor', 'Wollen Sie das Profil ')+self.profileComboBox.currentText()+translate('csveditor', ' wirklich löschen?'), "", "", translate('csveditor', "Ja"), translate('csveditor', "Nein"))
        if ok:
            self.profiles.pop(self.profileComboBox.currentText())
            self.loadProfiles()

    def removeCurrentSignal(self):
        idx = self.signalListWidget.currentRow()
        if idx <self.signalListWidget.count()-1 and self.signalListWidget.count()>=1:
            self.signalListWidget.takeItem(idx)
            self.signals.pop(idx)

    def addNewSignal(self, elementStr):
        if elementStr == '+':
            self.addSignal()

        self.updateSignalNames()

    def addSignal(self, setup=['','',0,0,'']):
        self.signalListWidget.takeItem(self.signalListWidget.count()-1)
        self.signals.append(csvSignalWidget.CsvSignalWidget(self, setup))
        itemN = QtGui.QListWidgetItem()
        s = self.signals[-1].sizeHint()
        s.setHeight(40)
        itemN.setSizeHint(s)
        #itemN.setMinimumHeight(50)

        #Add widget to QListWidget funList
        self.signalListWidget.addItem(itemN)
        self.signalListWidget.setItemWidget(itemN, self.signals[-1])
        self.signalListWidget.addItem('+')

    def clearSignals(self):
        self.signalListWidget.clear()
        self.signals = []
        self.signalListWidget.addItem('+')

    def importToLogger(self):
        signals = []
        for s in self.signals:
            sig = s.getSignal()
            if sig != None:
                signals.append(sig)
        if self.sendSignals:
            self.sendSignals(signals)
        else:
            print(signals)

    def updateSignalNames(self):
        oldS = translate('csveditor', 'Signal')
        oldD = translate('csveditor', 'Imported')
        oldU = ''
        for s in self.signals:
            oldD, oldS, oldU = s.updateName(oldD, oldS, oldU)

    def validateSignals(self):
        for s in self.signals:
            s.checkValidity()

    def closeEvent(self, event, *args, **kwargs):
        super(RTOC_Import, self).closeEvent(event)

if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    main = RTOC_Import('testdaten2.csv')
    main.show()
    sys.exit(app.exec_())

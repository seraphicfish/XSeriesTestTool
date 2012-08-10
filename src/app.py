'''
Created on 11/06/2012

@author: neville
'''
import sys
from decoder import *
from serial_app import *
from PyQt4 import QtCore, QtGui, QtSql
from gui.analyzer import Ui_MainWindow
from gui.maxrowsdialog import Ui_Dialog
from gui.packetview import Ui_packetViewer
 
class XPacketDB:
    def __init__(self):
        self.db = QtSql.QSqlDatabase.addDatabase("QSQLITE")
        self.db.setDatabaseName("test.db")
        self.db.open()
        self.model = QtSql.QSqlQueryModel()
        self.setupDecoder()
        
    def setupDecoder(self):
        xmetadata = metaRepository('settings/')
        self.xdec = XProtocolDecoder(xmetadata)
        self.xdec.registerTypeDecoder('integer-reverse', reverseIntegerDecoder)
        self.xdec.registerTypeDecoder('currency-reverse', reverseCurrencyDecoder)
        self.xdec.registerTypeDecoder('boolean', booleanDecoder)
        self.xdec.registerTypeDecoder('ascii-reverse', reverseAsciiDecoder)
    
    def getModel(self):
        return self.model
    
    def clearDatabase(self):
        query = "DELETE FROM packetlog"
        q = QtSql.QSqlQuery(self.db)
        q.exec_(query)
    
    def getDecodedData(self, rowindex):
        packet = self.getRawData(rowindex)
        seq = [x for x in bytearray.fromhex(packet)]
        return self.xdec.createXMLPacket(seq)
    
    def getRawData(self, rowindex):
        assert(isinstance(rowindex, int))
        record = self.model.record(rowindex)
        return str(record.value("hex").toString())
    
    def __del__(self):
        self.db.close()

class MaxRowsDialog(QtGui.QDialog):
    def __init__(self, parent=None):
        QtGui.QDialog.__init__(self, parent)
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setupConnections()
    
    def setupConnections(self):
        pass
           
class DecoderDialog(QtGui.QDialog):
    def __init__(self, parent=None):
        QtGui.QDialog.__init__(self, parent)
        self.ui = Ui_packetViewer()
        self.ui.setupUi(self)
        self.setupConnections()
    
    def setRawMsg(self, message):
        self.ui.lineEdit.setText(message)
    
    def setDecodedMsg(self, message):
        self.ui.textEdit.setText(message)
        
    def setupConnections(self):
        self.ui.btnCopy.clicked.connect(self.on_btnCopy_clicked)
        
    def on_btnCopy_clicked(self):
        self.ui.textEdit.selectAll()
        self.ui.textEdit.copy()
 
class MyApp(QtGui.QMainWindow):
    def __init__(self, parent=None):
        QtGui.QMainWindow.__init__(self, parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setupDB()
        self.setupChildDialogs()
        self.setupConnections()
        self.recording = False
        self.commThread = CommsThread()
        self.replayThread = ReplayThread()
        
    def setupChildDialogs(self):
        self.decDialog = DecoderDialog(self)
        self.maxRowsDialog = MaxRowsDialog(self)
    
    def setupDB(self):
        self.db = XPacketDB()
        self.ui.tableView.setModel(self.db.getModel())
        self.query = "SELECT * FROM packetlog ORDER BY timestamp DESC LIMIT 25"
        self.updateViewContents()
        
    def setupConnections(self):
        # set up connection to selection of record
        # some bugs here regarding current row is not selected
        self.ui.tableView.selectionModel().currentRowChanged.connect(self.decodeSelectedPacket)
        self.ui.btnRefresh.clicked.connect(self.on_btnRefresh_clicked)
        self.ui.btnAnalyze.clicked.connect(self.on_btnAnalyze_clicked)
        self.ui.btnClear.clicked.connect(self.on_btnClear_clicked)
        self.ui.btnRecordPause.clicked.connect(self.on_btnRecordPause_clicked)
        self.ui.pushButton.clicked.connect(self.on_btnReplay_clicked)
        
        self.ui.actionSet_Maximum_Rows.triggered.connect(self.on_MaxRowsAction_triggered)
        self.ui.checkBox.toggled.connect(self.on_autoRefreshCheckBoxToggled)

    def on_autoRefreshCheckBoxToggled(self):
        if self.ui.checkBox.isChecked():
            self.connect(self.commThread, SIGNAL("receivedpacket"), self.on_btnRefresh_clicked)
        else:
            self.disconnect(self.commThread, SIGNAL("receivedpacket"), self.on_btnRefresh_clicked)
    
    def on_btnRecordPause_clicked(self):
        if not self.recording:
            self.ui.btnRecordPause.setText("Pause")
            self.ui.lineEditPort.setDisabled(True)
            self.recording = True
            portname = str(self.ui.lineEditPort.text())
            self.commThread.setcommport(portname)
            self.commThread.setbaud(9600)
            self.commThread.start()
        else:
            self.ui.btnRecordPause.setText("Record")
            self.ui.lineEditPort.setDisabled(False)
            self.recording = False
            self.commThread.quit()
            
    def on_btnReplay_clicked(self):
        portname = str(self.ui.lineEditPort.text())
        self.replayThread.setcommport(portname)
        self.replayThread.setbaud(9600)
        self.replayThread.start()
    
    def on_MaxRowsAction_triggered(self):
        self.maxRowsDialog.exec_()
        
    def on_btnClear_clicked(self):
        self.db.clearDatabase()
        self.updateViewContents()
    
    def on_btnAnalyze_clicked(self):
        self.decDialog.show()
        
    def on_btnRefresh_clicked(self):
        # updates query from user specified SQL statement
        self.query = self.ui.lineEdit.text()
        self.updateViewContents()
    
    def updateViewContents(self):
        self.ui.lineEdit.setText(self.query)
        self.db.getModel().setQuery(self.query)
        self.ui.tableView.selectRow(0)
        self.ui.tableView.resizeColumnsToContents()
        
    def decodeSelectedPacket(self):
        index = self.ui.tableView.currentIndex().row()
        self.decDialog.setDecodedMsg(self.db.getDecodedData(index))
        self.decDialog.setRawMsg(self.db.getRawData(index))
        
if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    myapp = MyApp()
    myapp.show()
    sys.exit(app.exec_())

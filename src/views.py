"""
XSeriesTestTool - A NSW gaming protocol decoder/analyzer
    Copyright (C) 2012  Neville Tummon

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import sqlite3
from datetime import datetime
from debug import *
from PyQt4.QtCore import QObject, SIGNAL, Qt
from PyQt4 import QtSql, QtGui

class QtSQLWrapper(QObject):
    def __init__(self, filename, parent = None):
        QObject.__init__(self, parent)
        self.db = QtSql.QSqlDatabase.addDatabase("QSQLITE")
        self.db.setDatabaseName(filename)
        self.db.open()

        self.createSQLTables()
        self.setupSourceModels()
        self.setupProxyModels()
        self.filter = DuplicateDatablockFilter()
        self.filter.filterduplicates(True)

    def setupSourceModels(self):
        self.model = QtSql.QSqlTableModel(self)
        self.model.setTable("distinctpackets")
        self.model.sort(0, Qt.DescendingOrder)

        self.sessionmodel = QtSql.QSqlRelationalTableModel(self)
        self.sessionmodel.setTable("session")
        self.sessionmodel.setRelation(1, QtSql.QSqlRelation("distinctpackets", "ID", "Class"))
        self.sessionmodel.sort(0, Qt.DescendingOrder)

    def setupProxyModels(self):
        self.proxy = QtGui.QSortFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterKeyColumn(3)
        self.proxy.setDynamicSortFilter(True)
        
        self.sessionproxy = QtGui.QSortFilterProxyModel()
        self.sessionproxy.setSourceModel(self.sessionmodel)
        self.sessionproxy.setFilterKeyColumn(1)
        self.sessionproxy.setDynamicSortFilter(True)

    def createSQLTables(self):
        self.query = QtSql.QSqlQuery(self.db)
        sql = """CREATE TABLE IF NOT EXISTS session(
        Timestamp DATETIME,
        PacketID INTEGER NOT NULL)"""
        self.query.prepare(sql)
        self.query.exec_()
        sql = """CREATE TABLE IF NOT EXISTS distinctpackets(
        ID INTEGER PRIMARY KEY,
        LastChanged DATETIME,
        Direction TEXT NOT NULL,
        Class TEXT NOT NULL,
        Data TEXT NOT NULL)"""
        self.query.prepare(sql)
        self.query.exec_()
        self.query.finish()

    def addRecord(self, direction, type, bytearray):
        hexstring = ''.join(["%02X" % byte for byte in bytearray])
        loggedtime = str(datetime.now())
        
        if self.filter.differentToPrevious(type, bytearray):
            self.query.prepare("INSERT INTO distinctpackets(LastChanged, Direction, Class, Data) VALUES(:date,:direction,:type,:contents)")
            self.query.bindValue(":date", loggedtime)
            self.query.bindValue(":direction", str(direction))
            self.query.bindValue(":type", type)
            self.query.bindValue(":contents", str(hexstring))
            self.query.exec_()
            self.query.finish()
        
        sql = """SELECT MAX(ID)
        FROM distinctpackets 
        WHERE Class = '%s'
        AND Direction = 'incoming'""" % type
        id = self.runSelectQuery(sql)
        
        self.query.prepare("INSERT INTO session(Timestamp, PacketID) VALUES(:date,:packetid)")
        self.query.bindValue(":date", loggedtime)
        self.query.bindValue(":packetid", id[0])
        self.query.exec_()
        self.query.finish()
        self.emit(SIGNAL("newentry"))

    def refresh(self):
        self.model.select()
        self.sessionmodel.select()
        #self.model.setQuery("SELECT * FROM packetlog ORDER BY timestamp DESC LIMIT 200")

    def setAutoRefresh(self, toggle):
        if toggle == True:
            self.connect(self, SIGNAL("newentry"), self.refresh)
        else:
            self.disconnect(self, SIGNAL("newentry"), self.refresh)

    #def filterduplicates(self, toggle):
    #    self.filter.filterduplicates(toggle)

    def getProxyModel(self):
        return self.proxy
    
    def getSessionProxy(self):
        return self.sessionproxy

    def clearDatabase(self):
        self.query.exec_("DELETE FROM session")
        self.query.exec_("DELETE FROM distinctpackets")
        self.query.finish()
        self.refresh()

    def runSelectQuery(self, query):
        if self.query.isActive():
            DBGLOG("Wrapper: previous query is still active")
            return []
        self.query.prepare(query)
        if self.query.exec_():
            list = []
            while self.query.next():
                list.append(str(self.query.value(0).toString()))
            DBGLOG("Wrapper: %i" % len(list))
            return list
        DBGLOG("Wrapper: query did not execute successfully")
        return []

    def __del__(self):
        self.db.close()

class DuplicateDatablockFilter:
    def __init__(self):
        self.dupes = {}
        self.filterduplicates(False)

    def filterduplicates(self, toggle):
        assert(isinstance(toggle, bool))
        self.filtered = toggle
        self.dupes.clear()
        DBGLOG("DDFilter: Filtering enabled = %s" % toggle)

    def differentToPrevious(self, blocktype, seq):
        if not self.filtered:
            return True

        key = blocktype
        data = self.dupes.get(key)
        if data is None:
            DBGLOG("DDFilter: NEW DATABLOCK!")
            self.dupes[key] = seq
            return True

        assert(len(seq) == len(data))
        for i in range(len(seq)):
            if seq[i] != data[i]:
                self.dupes[key] = seq
                assert(seq == self.dupes.get(key))
                DBGLOG("DDFilter: DIFFERENT DATABLOCK!")
                return True
        DBGLOG("DDFilter: REPEATED!")
        return False
# This file is part of the Frescobaldi project, http://www.frescobaldi.org/
#
# Copyright (c) 2008 - 2012 by Wilbert Berendsen
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
# See http://www.gnu.org/licenses/ for more information.

"""
The Music View's Edit in Place dialog.
"""

from __future__ import unicode_literals

from PyQt4.QtCore import *
from PyQt4.QtGui import *

import app
import cursordiff
import cursortools
import help
import highlighter
import homekey
import indent
import matcher
import metainfo
import qutil
import textformats
import tokeniter
import widgets.dialog

from . import tooltip


def edit(parent, cursor, position=None):
    dlg = Dialog(parent)
    dlg.finished.connect(dlg.deleteLater)
    dlg.edit(cursor)
    dlg.popup(position)


class Dialog(widgets.dialog.Dialog):
    """Dialog containing a short text edit field to edit one line."""
    def __init__(self, parent=None):
        super(Dialog, self).__init__(parent)
        self._document = None
        self.messageLabel().setWordWrap(True)
        self.document = d = QTextDocument()
        d.setDocumentLayout(QPlainTextDocumentLayout(d))
        self.highlighter = highlighter.highlighter(d)
        self.view = View(d)
        self.matcher = Matcher(self.view)
        self.setMainWidget(self.view)
        app.translateUI(self)
        help.addButton(self.buttonBox(), help_musicview_editinplace)
        # make Ctrl+Return accept the dialog
        self.button("ok").setShortcut(QKeySequence("Ctrl+Return"))
        qutil.saveDialogSize(self, "musicview/editinplace/dialog/size")
        
        self.accepted.connect(self.save)
    
    def translateUI(self):
        self.setWindowTitle(app.caption(_("Edit in Place")))
        self.updateMessage()
    
    def edit(self, cursor):
        """Edit the block at the specified QTextCursor."""
        if self._document:
            self._document.closed.disconnect(self.reject)
        self._document = cursor.document()
        self._document.closed.connect(self.reject)
        
        # dont change the cursor
        c = self._range = QTextCursor(cursor)
        cursorpos = c.position() - c.block().position()
        cursortools.strip_indent(c)
        indentpos = c.position() - c.block().position()
        c.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        self.view.setPlainText(c.selection().toPlainText())
        
        self.highlighter.setInitialState(tokeniter.state(cursor))
        self.highlighter.setHighlighting(metainfo.info(cursor.document()).highlighting)
        self.highlighter.rehighlight()
        
        cursor = self.view.textCursor()
        cursor.setPosition(max(0, cursorpos-indentpos))
        self.view.setTextCursor(cursor)
        
        self.updateMessage()
        
    def popup(self, position):
        """Show the dialog at the specified global QPoint."""
        geom = self.geometry()
        geom.moveCenter(position)
        if position.y() <= geom.height() + 60:
            geom.moveTop(position.y() + 60)
        else:
            geom.moveBottom(position.y() - 60)
        self.setGeometry(geom)
        self.view.setFocus()
        self.show()
    
    def save(self):
        """Called to perform the edits in the document."""
        cursor = QTextCursor(self._range)
        start = cursor.selectionStart()
        with cursortools.compress_undo(cursor):
            # use cursordiff; dont destroy point and click positions
            cursordiff.insert_text(cursor, self.view.toPlainText())
            cursor.setPosition(start, QTextCursor.KeepAnchor)
            # re-indent the inserted line(s)
            indent.re_indent(cursor)
        
    def updateMessage(self):
        """Called when a new cursor is set to edit, updates the message text."""
        if self._document:
            self.setMessage(
              _("Editing line {linenum} of \"{document}\" ({variable})").format(
                linenum = self._range.block().blockNumber() + 1,
                document = self._document.documentName(),
                variable = tooltip.get_definition(self._range) or _("<unknown>"),
            ))
        else:
            self.setMessage("<no document set>") # should never appear


class View(QPlainTextEdit):
    """The text edit in the "Edit in Place" dialog."""
    def __init__(self, document):
        super(View, self).__init__()
        self.setDocument(document)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setCursorWidth(2)
        app.settingsChanged.connect(self.readSettings)
        self.readSettings()
    
    def readSettings(self):
        data = textformats.formatData('editor')
        self.setFont(data.font)
        self.setPalette(data.palette())
    
    def sizeHint(self):
        metrics = self.fontMetrics()
        return QSize(80 * metrics.width(" "),3 * metrics.height())
    
    def event(self, ev):
        """Reimplemented to avoid typing the line separator."""
        if ev == QKeySequence.InsertLineSeparator:
            return False
        return super(View, self).event(ev)


class Matcher(matcher.MatcherBase):
    def __init__(self, view):
        self.view = view
        self.highlighter = MatchHighlighter(view)
        view.cursorPositionChanged.connect(self.checkMatches)
    
    def checkMatches(self):
        self.showMatches(self.view, self.highlighter)


class MatchHighlighter(widgets.arbitraryhighlighter.ArbitraryHighlighter):
    def __init__(self, edit):
        super(MatchHighlighter, self).__init__(edit)
        app.settingsChanged.connect(self.readSettings)
        self.readSettings()
    
    def readSettings(self):
        self._baseColors = textformats.formatData('editor').baseColors
        self.reload()
    
    def textFormat(self, name):
        f = QTextCharFormat()
        f.setBackground(self._baseColors[name])
        return f


class help_musicview_editinplace(help.page):
    def title():
        return _("Edit in place")
    
    def body():
        return ''.join(map('<p>{0}</p>\n'.format, (
        _("In this dialog you can edit one line of the text document."),
        _("Click OK or press {key} to place the modified text in the document.").format(
        key=QKeySequence("Ctrl+Return").toString(QKeySequence.NativeText)),
        _("You can open the \"Edit in Place\" dialog by Shift-clicking a "
          "clickable object in the Music View or by right-clicking the object "
          "and selecting {menu}.").format(menu=help.menu(_("Edit in Place"))),
        )))


# xl-Screenshot and xl-Annotate
# Copyright (C) 2026 Wesley Hayslip
#
# This program is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software Foundation,
# either version 3 of the License, or (at your option) any later version.
# It is distributed WITHOUT ANY WARRANTY; see <https://www.gnu.org/licenses/>.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Translations (gettext): _() for text people see, N_() for names translated when shown.

Both apps share one text domain, xl-screenshot, since they are one package.
"""
import gettext
import locale
import os


# Translations: share/locale/<language>/LC_MESSAGES/xl-screenshot.mo, three folders up
# from this file. That is /usr/share/locale once installed, and usr/share/locale in the
# source folder after "make".
TEXT_DOMAIN = "xl-screenshot"
LOCALE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                           "..", "..", "..", "share", "locale"))
try:
    locale.setlocale(locale.LC_ALL, "")
except locale.Error:
    pass
gettext.bindtextdomain(TEXT_DOMAIN, LOCALE_DIR)
gettext.textdomain(TEXT_DOMAIN)
_ = gettext.gettext
ngettext = gettext.ngettext         # for text with a number in it: "1 second", "3 seconds"


def N_(text):
    """Marks text for translation where it is also used as a name in the code (a colour,
    a tool); it is translated with _() only when shown."""
    return text

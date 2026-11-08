# xl-Screenshot and xl-Annotate: build the translations and install the programs.
#
#   make           compile po/*.po, and write the menu entries and Nemo item with their translations
#   make pot       update po/xl-screenshot.pot from the source (after changing any text)
#   make install   copy everything into $(DESTDIR)$(PREFIX); debian/rules runs this
#   make deb       build the .deb (in the folder above this one)
#   make check     run the tests (needs xvfb, openbox, xdotool: see tests/README.md)
#   make clean     remove what make built

DOMAIN  = xl-screenshot
VERSION = $(shell sed -n '1s/.*(\(.*\)).*/\1/p' debian/changelog)
PREFIX ?= /usr
LIBDIR  = $(PREFIX)/lib/xl-screenshot
SHARE   = $(PREFIX)/share

# The Python code: one folder per app, plus what both share
PACKAGES = xlscreenshot xlannotate xlshared
SOURCES  = $(sort $(wildcard $(addprefix usr/lib/xl-screenshot/,$(addsuffix /*.py,$(PACKAGES)))))
APP_IDS  = io.github.xlcheese.XlScreenshot io.github.xlcheese.XlAnnotate
COMMANDS = xl-screenshot xl-annotate
ICON_SIZES = scalable 32x32 24x24 16x16

# Menu entries and the Nemo item, written from data/*.in with their translations
DESKTOP  = $(foreach id,$(APP_IDS),usr/share/applications/$(id).desktop)
NEMO     = usr/share/nemo/actions/xl-annotate.nemo_action
TEMPLATES = $(addprefix data/,$(addsuffix .desktop.in,$(APP_IDS)) xl-annotate.nemo_action.in)
LOCALE   = usr/share/locale
LANGUAGES = $(shell grep -v "^\s*#" po/LINGUAS)
MO_FILES = $(foreach lang,$(LANGUAGES),$(LOCALE)/$(lang)/LC_MESSAGES/$(DOMAIN).mo)
# the words in those files that are translated (the app names are marked "leave as it is")
DESKTOP_KEYWORDS = --keyword= --keyword=Name --keyword=GenericName --keyword=Comment --keyword=Keywords

all: $(MO_FILES) $(DESKTOP) $(NEMO)

$(LOCALE)/%/LC_MESSAGES/$(DOMAIN).mo: po/%.po
	mkdir -p $(dir $@)
	msgfmt --check --output-file=$@ $<

usr/share/applications/%.desktop: data/%.desktop.in $(wildcard po/*.po)
	mkdir -p $(dir $@)
	msgfmt --desktop $(DESKTOP_KEYWORDS) --template=$< -d po --output-file=$@

$(NEMO): data/xl-annotate.nemo_action.in $(wildcard po/*.po)
	mkdir -p $(dir $@)
	msgfmt --desktop $(DESKTOP_KEYWORDS) --template=$< -d po --output-file=$@

POT_HEADER = --package-name=xl-Screenshot --package-version=$(VERSION) --copyright-holder="Wesley Hayslip" \
	--msgid-bugs-address=https://github.com/xlcheese/xl-screenshot/issues

pot:
	xgettext --language=Python --from-code=UTF-8 --keyword=_ --keyword=N_ --add-comments=Translators \
		$(POT_HEADER) --output=po/$(DOMAIN).pot $(SOURCES)
	xgettext --language=Desktop $(DESKTOP_KEYWORDS) --add-comments=Translators --join-existing \
		$(POT_HEADER) --output=po/$(DOMAIN).pot $(TEMPLATES)
	for po in $(wildcard po/*.po); do msgmerge --quiet --update --backup=none $$po po/$(DOMAIN).pot; done

install: all
	install -d $(DESTDIR)$(PREFIX)/bin
	install -m755 $(addprefix usr/bin/,$(COMMANDS)) $(DESTDIR)$(PREFIX)/bin/
	for pkg in $(PACKAGES); do \
		install -d $(DESTDIR)$(LIBDIR)/$$pkg; \
		install -m644 usr/lib/xl-screenshot/$$pkg/*.py $(DESTDIR)$(LIBDIR)/$$pkg/; \
	done
	for id in $(APP_IDS); do \
		install -Dm644 usr/share/applications/$$id.desktop $(DESTDIR)$(SHARE)/applications/$$id.desktop; \
		install -Dm644 usr/share/metainfo/$$id.metainfo.xml $(DESTDIR)$(SHARE)/metainfo/$$id.metainfo.xml; \
		for size in $(ICON_SIZES); do \
			install -Dm644 usr/share/icons/hicolor/$$size/apps/$$id.svg \
				$(DESTDIR)$(SHARE)/icons/hicolor/$$size/apps/$$id.svg; \
		done; \
	done
	install -d $(DESTDIR)$(SHARE)/icons/hicolor/scalable/actions
	install -m644 usr/share/icons/hicolor/scalable/actions/*.svg $(DESTDIR)$(SHARE)/icons/hicolor/scalable/actions/
	install -Dm644 $(NEMO) $(DESTDIR)$(SHARE)/nemo/actions/xl-annotate.nemo_action
	for cmd in $(COMMANDS); do \
		install -Dm644 usr/share/man/man1/$$cmd.1 $(DESTDIR)$(SHARE)/man/man1/$$cmd.1; \
	done
	for lang in $(LANGUAGES); do \
		install -Dm644 $(LOCALE)/$$lang/LC_MESSAGES/$(DOMAIN).mo \
			$(DESTDIR)$(SHARE)/locale/$$lang/LC_MESSAGES/$(DOMAIN).mo; \
	done

check: all
	tests/run-tests

deb:
	dpkg-buildpackage --build=binary --no-sign

clean:
	rm -rf $(LOCALE) usr/share/applications $(NEMO)
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

.PHONY: all pot install check deb clean

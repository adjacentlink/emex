ACLOCAL_AMFLAGS = -I m4

EXTRA_DIST= \
 autogen.sh \
 emex \
 waveform_resource \
 scripts \
 Copyright \
 debian \
 $(PACKAGE).spec.in \
 emex/common.proto \
 emex/emexd.proto \
 emex/emexcontainer.proto \
 emex/emexscenario.proto \
 setup.py.in \
 emex/emexd.xml.in

all-local: setup.py emex/common_pb2.py emex/emexd_pb2.py emex/emexcontainer_pb2.py emex/emexscenario_pb2.py emex/emexd.xml
	$(PYTHON) setup.py build


clean-local: setup.py
	$(PYTHON) setup.py clean
	-rm -rf python*.egg-info
	-rm -rf build
	-rm -rf dist
	-rm -f emex*tar.gz
	-rm -f setup.py
	-rm -f MANIFEST
	-rm -f installed.txt
	-rm -f `find . -name "*\.pyc"`
	-rm -f `find . -name "*~"`
	-rm -f emex/common_pb2.py
	-rm -f emex/emexd_pb2.py
	-rm -f emex/emexcontainer_pb2.py
	-rm -f emex/emexscenario_pb2.py
	-rm -f emex/emexd.xml
	-rm -f emex*.pdf
	-rm -rf .debbuild
	-rm -rf .rpmbuild
	-rm -rf $(PACKAGE).spec
	-rm -rf emex/__pycache__
	-rm -rf emex/data/__pycache__
	-rm -rf emex/helpers/__pycache__
	-rm -rf waveform_resource/__pycache__
	-rm -rf waveform_resource/plugins/__pycache__
	-rm -rf waveform_resource/plugins/emex/__pycache__


install: setup.py
	$(PYTHON) setup.py install \
	    -O1 \
        --record .installedfiles \
	    --prefix=$(prefix) \
	    --exec-prefix=$(exec_prefix) \
	    $(if $(DESTDIR),--root=$(DESTDIR))

uninstall:
	if test -f .installedfiles; then xargs -a .installedfiles rm -f; fi

spec: setup.py
	$(PYTHON) setup.py bdist_rpm --spec-only


edit = sed \
        -e 's|@VERSION[@]|$(VERSION)|g' \
        -e 's|@DEBIAN_VERSION[@]|$(DEBIAN_VERSION)|g' \
        -e 's|@DATE_RFC2822[@]|$(DATE_RFC2822)|g'

if HAVE_RPMBUILD

RPMARCH=`arch`

RPMBUILD_ARGS=

rpm: $(PACKAGE).spec dist-gzip
	mkdir -p .rpmbuild/BUILD \
	.rpmbuild/SPECS \
	.rpmbuild/SOURCES \
	.rpmbuild/SRPMS \
	.rpmbuild/RPMS/noarch \
	.rpmbuild/tmp
	cp -f $(PACKAGE)-$(VERSION).tar.gz .rpmbuild/SOURCES
	rpmbuild --clean -ba $(top_srcdir)/$(PACKAGE).spec --target $(RPMARCH) \
    --define "_topdir $$PWD/.rpmbuild" \
    --define "_tmppath $$PWD/.rpmbuild/tmp" \
    $(RPMBUILD_ARGS)
	@echo "============================================================"
	@echo "RPMs located in .rpmbuild/RPMS and .rpmbuild/SRPMS"

endif

if HAVE_DEB

deb: dist-gzip
	rm -rf .debbuild
	mkdir -p .debbuild
	cp -f $(PACKAGE)-$(VERSION).tar.gz .debbuild
	cd .debbuild && tar xzf $(PACKAGE)-$(VERSION).tar.gz
	$(edit) .debbuild/$(PACKAGE)-$(VERSION)/debian/changelog.in > \
          .debbuild/$(PACKAGE)-$(VERSION)/debian/changelog
	cd .debbuild/$(PACKAGE)-$(VERSION) && dpkg-buildpackage -F -us -uc
	@echo "============================================================"
	@echo "debs located in .debbuild"
cleandeb:
	dh_clean
else

cleandeb:

endif

$(PACKAGE).spec: $(PACKAGE).spec.in
	if test -f $@; then chmod u+w $@; fi
	$(edit) $< > $@
	chmod g-w,u-w $@

setup.py: setup.py.in
	if test -f $@; then chmod u+w $@; fi
	$(edit) $< > $@
	chmod g-w,u-w $@

emex/common_pb2.py: emex/common.proto
	protoc --python_out=. -I. $<

emex/emexd_pb2.py: emex/emexd.proto
	protoc --python_out=. -I. $<

emex/emexcontainer_pb2.py: emex/emexcontainer.proto
	protoc --python_out=. -I. $<

emex/emexscenario_pb2.py: emex/emexscenario.proto
	protoc --python_out=. -I. $<

emex/emexd.xml: emex/emexd.xml.in
	if test -f $@; then chmod u+w $@; fi
	$(edit) $< > $@
	chmod g-w,u-w $@

if HAVE_PANDOC
emex.pdf: emex.md
	pandoc --variable urlcolor=cyan  $< -o $@ -f \
         markdown+raw_tex+header_attributes+multiline_tables -V colorlinks

pdf: emex.pdf
endif

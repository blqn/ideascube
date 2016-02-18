from hashlib import sha256

import pytest
from resumable import DownloadCheck, DownloadError


@pytest.fixture(
    params=[
        {
            'id': 'foo',
            'name': 'Content provided by Foo',
            'url': 'http://foo.fr/catalog.yml',
        },
        {
            'name': 'Content provided by Foo',
            'url': 'http://foo.fr/catalog.yml',
        },
        {
            'id': 'foo',
            'url': 'http://foo.fr/catalog.yml',
        },
        {
            'id': 'foo',
            'name': 'Content provided by Foo',
        },
    ],
    ids=[
        'foo',
        'missing-id',
        'missing-name',
        'missing-url',
    ])
def input_file(tmpdir, request):
    path = tmpdir.join('foo.yml')

    if 'id' in request.param:
        path.write('id: {id}\n'.format(**request.param), mode='a')

    if 'name' in request.param:
        path.write('name: {name}\n'.format(**request.param), mode='a')

    if 'url' in request.param:
        path.write('url: {url}'.format(**request.param), mode='a')

    return {'path': path.strpath, 'input': request.param}


@pytest.fixture
def zippedzim_path(testdatadir, tmpdir):
    zippedzim = testdatadir.join('catalog', 'wikipedia.tum-2015-08')
    path = tmpdir.mkdir('packages').join('wikipedia.tum-2015-08')
    zippedzim.copy(path)

    return path


@pytest.fixture
def install_dir(tmpdir):
    return tmpdir.mkdir('install')


# This is starting to look a lot like adding file:// support to
# resumable.urlretrieve...
# TODO: Do they want it upstream?
def fake_urlretrieve(url, path, reporthook=None, sha256sum=None):
    assert url.startswith('file://')

    src = url[7:]

    with open(src, 'rb') as in_, open(path, 'a+b') as out:
        out.seek(0)
        already = len(out.read())

        in_.seek(already)
        out.seek(already)
        out.write(in_.read())

    if sha256sum is not None:
        with open(path, 'rb') as f:
            checksum = sha256(f.read()).hexdigest()

        if sha256sum != checksum:
            raise DownloadError(DownloadCheck.checksum_mismatch)


def test_remote_from_file(input_file):
    from ideascube.serveradmin.catalog import InvalidFile, Remote

    path = input_file['path']
    expected_id = input_file['input'].get('id')
    expected_name = input_file['input'].get('name')
    expected_url = input_file['input'].get('url')

    if expected_id is None:
        with pytest.raises(InvalidFile) as exc:
            Remote.from_file(path)

        assert 'id' in exc.exconly()

    elif expected_name is None:
        with pytest.raises(InvalidFile) as exc:
            Remote.from_file(path)

        assert 'name' in exc.exconly()

    elif expected_url is None:
        with pytest.raises(InvalidFile) as exc:
            Remote.from_file(path)

        assert 'url' in exc.exconly()

    else:
        remote = Remote.from_file(path)
        assert remote.id == expected_id
        assert remote.name == expected_name
        assert remote.url == expected_url


def test_remote_to_file(tmpdir):
    from ideascube.serveradmin.catalog import Remote

    path = tmpdir.join('foo.yml')

    remote = Remote(
        'foo', 'Content provided by Foo', 'http://foo.fr/catalog.yml')
    remote.to_file(path.strpath)

    lines = path.readlines(cr=False)
    lines = filter(lambda x: len(x), lines)
    lines = sorted(lines)

    assert lines == [
        'id: foo', 'name: Content provided by Foo',
        'url: http://foo.fr/catalog.yml']


def test_package():
    from ideascube.serveradmin.catalog import Package

    p = Package('wikipedia.fr', {
        'name': 'Wikipédia en français', 'version': '2015-08'})
    assert p.id == 'wikipedia.fr'
    assert p.name == 'Wikipédia en français'
    assert p.version == '2015-08'

    with pytest.raises(AttributeError):
        print(p.no_such_attribute)

    with pytest.raises(NotImplementedError):
        p.install('some-path', 'some-other-path')

    with pytest.raises(NotImplementedError):
        p.remove('some-path')


def test_package_without_version():
    from ideascube.serveradmin.catalog import Package

    p = Package('wikipedia.fr', {'name': 'Wikipédia en français'})
    assert p.id == 'wikipedia.fr'
    assert p.name == 'Wikipédia en français'
    assert p.version == '0'


def test_package_equality():
    from ideascube.serveradmin.catalog import Package

    p1 = Package('wikipedia.fr', {
        'name': 'Wikipédia en français', 'version': '2015-08',
        'type': 'zippedzim'})
    p2 = Package('wikipedia.en', {
        'name': 'Wikipédia en français', 'version': '2015-08',
        'type': 'zippedzim'})
    assert p1 != p2

    p3 = Package('wikipedia.fr', {
        'name': 'Wikipédia en français', 'version': '2015-09',
        'type': 'zippedzim'})
    assert p1 != p3

    p4 = Package('wikipedia.fr', {
        'name': 'Wikipédia en français', 'type': 'zippedzim',
        'version': '2015-08'})
    assert p1 == p4


def test_package_registry():
    from ideascube.serveradmin.catalog import Package

    # Ensure the base type itself is not added to the registry
    assert Package not in Package.registered_types.values()

    # Register a new package type, make sure it gets added to the registry
    class RegisteredPackage(Package):
        typename = 'tests-only'

    assert Package.registered_types['tests-only'] == RegisteredPackage

    # Define a new package type without a typename attribute, make sure it
    # does **not** get added to the registry
    class NotRegisteredPackage(Package):
        pass

    assert NotRegisteredPackage not in Package.registered_types.values()


def test_install_zippedzim(zippedzim_path, install_dir):
    from ideascube.serveradmin.catalog import ZippedZim

    p = ZippedZim('wikipedia.tum', {
        'url': 'https://foo.fr/wikipedia_tum_all_nopic_2015-08.zim'})
    p.install(zippedzim_path.strpath, install_dir.strpath)

    data = install_dir.join('data')
    assert data.check(dir=True)

    content = data.join('content')
    assert content.check(dir=True)
    assert content.join('{}.zim'.format(p.id)).check(file=True)

    lib = data.join('library')
    assert lib.check(dir=True)
    assert lib.join('{}.zim.xml'.format(p.id)).check(file=True)

    index = data.join('index')
    assert index.check(dir=True)
    assert index.join('{}.zim.idx'.format(p.id)).check(dir=True)


def test_install_invalid_zippedzim(tmpdir, testdatadir, install_dir):
    from ideascube.serveradmin.catalog import ZippedZim, InvalidFile

    src = testdatadir.join('backup', 'musasa-0.1.0-201501241620.tar')
    path = tmpdir.mkdir('packages').join('wikipedia.tum-2015-08')
    src.copy(path)

    p = ZippedZim('wikipedia.tum', {
        'url': 'https://foo.fr/wikipedia_tum_all_nopic_2015-08.zim'})

    with pytest.raises(InvalidFile) as exc:
        p.install(path.strpath, install_dir.strpath)

    assert 'not a zip file' in exc.exconly()


def test_remove_zippedzim(zippedzim_path, install_dir):
    from ideascube.serveradmin.catalog import ZippedZim

    p = ZippedZim('wikipedia.tum', {
        'url': 'https://foo.fr/wikipedia_tum_all_nopic_2015-08.zim'})
    p.install(zippedzim_path.strpath, install_dir.strpath)

    p.remove(install_dir.strpath)

    data = install_dir.join('data')
    assert data.check(dir=True)

    content = data.join('content')
    assert content.check(dir=True)
    assert content.join('{}.zim'.format(p.id)).check(exists=False)

    lib = data.join('library')
    assert lib.check(dir=True)
    assert lib.join('{}.zim.xml'.format(p.id)).check(exists=False)

    index = data.join('index')
    assert index.check(dir=True)
    assert index.join('{}.zim.idx'.format(p.id)).check(exists=False)


def test_handler(tmpdir, settings):
    from ideascube.serveradmin.catalog import Handler

    # This is required to test the constructor of the base package
    Handler.typename = 'tests_only'

    settings.CATALOG_TESTS_ONLY_INSTALL_DIR = tmpdir.strpath
    h = Handler()
    assert h._install_dir == tmpdir.strpath

    with pytest.raises(NotImplementedError):
        h.commit()

    # Don't forget to delete that class attribute, or it impacts other tests
    del(Handler.typename)


def test_handler_registry():
    from ideascube.serveradmin.catalog import Handler

    # Ensure the base type itself is not added to the registry
    assert Handler not in Handler.registered_types.values()

    # Register a new handler type, make sure it gets added to the registry
    class RegisteredHandler(Handler):
        typename = 'tests-only'

    assert Handler.registered_types['tests-only'] == RegisteredHandler

    # Define a new handler type without a typename attribute, make sure it
    # does **not** get added to the registry
    class NotRegisteredHandler(Handler):
        pass

    assert NotRegisteredHandler not in Handler.registered_types.values()


def test_kiwix_handler(tmpdir, settings):
    from ideascube.serveradmin.catalog import Kiwix

    settings.CATALOG_KIWIX_INSTALL_DIR = tmpdir.strpath
    h = Kiwix()
    assert h._install_dir == tmpdir.strpath


def test_kiwix_installs_zippedzim(tmpdir, settings, zippedzim_path):
    from ideascube.serveradmin.catalog import Kiwix, ZippedZim

    settings.CATALOG_KIWIX_INSTALL_DIR = tmpdir.strpath

    p = ZippedZim('wikipedia.tum', {
        'url': 'https://foo.fr/wikipedia_tum_all_nopic_2015-08.zim'})
    h = Kiwix()
    h.install(p, zippedzim_path.strpath)

    data = tmpdir.join('data')
    assert data.check(dir=True)

    content = data.join('content')
    assert content.check(dir=True)
    assert content.join('{}.zim'.format(p.id)).check(file=True)

    lib = data.join('library')
    assert lib.check(dir=True)
    assert lib.join('{}.zim.xml'.format(p.id)).check(file=True)

    index = data.join('index')
    assert index.check(dir=True)
    assert index.join('{}.zim.idx'.format(p.id)).check(dir=True)


def test_kiwix_removes_zippedzim(tmpdir, settings, zippedzim_path):
    from ideascube.serveradmin.catalog import Kiwix, ZippedZim

    settings.CATALOG_KIWIX_INSTALL_DIR = tmpdir.strpath

    p = ZippedZim('wikipedia.tum', {
        'url': 'https://foo.fr/wikipedia_tum_all_nopic_2015-08.zim'})
    h = Kiwix()
    h.install(p, zippedzim_path.strpath)

    h.remove(p)

    data = tmpdir.join('data')
    assert data.check(dir=True)

    content = data.join('content')
    assert content.check(dir=True)
    assert content.join('{}.zim'.format(p.id)).check(exists=False)

    lib = data.join('library')
    assert lib.check(dir=True)
    assert lib.join('{}.zim.xml'.format(p.id)).check(exists=False)

    index = data.join('index')
    assert index.check(dir=True)
    assert index.join('{}.zim.idx'.format(p.id)).check(exists=False)


def test_kiwix_commits_after_install(tmpdir, settings, zippedzim_path, mocker):
    from ideascube.serveradmin.catalog import Kiwix, ZippedZim

    settings.CATALOG_KIWIX_INSTALL_DIR = tmpdir.strpath
    manager = mocker.patch('ideascube.serveradmin.catalog.SystemManager')

    p = ZippedZim('wikipedia.tum', {
        'url': 'https://foo.fr/wikipedia_tum_all_nopic_2015-08.zim'})
    h = Kiwix()
    h.install(p, zippedzim_path.strpath)
    h.commit()

    library = tmpdir.join('library.xml')
    assert library.check(exists=True)

    with library.open(mode='r') as f:
        libdata = f.read()

        assert 'path="data/content/wikipedia.tum.zim"' in libdata
        assert 'indexPath="data/index/wikipedia.tum.zim.idx"' in libdata

    manager().get_service.assert_called_once_with('kiwix-server')
    manager().restart.assert_called_once()


def test_kiwix_commits_after_remove(tmpdir, settings, zippedzim_path, mocker):
    from ideascube.serveradmin.catalog import Kiwix, ZippedZim
    from ideascube.serveradmin.systemd import NoSuchUnit

    settings.CATALOG_KIWIX_INSTALL_DIR = tmpdir.strpath
    manager = mocker.patch('ideascube.serveradmin.catalog.SystemManager')
    manager().get_service.side_effect = NoSuchUnit

    p = ZippedZim('wikipedia.tum', {
        'url': 'https://foo.fr/wikipedia_tum_all_nopic_2015-08.zim'})
    h = Kiwix()
    h.install(p, zippedzim_path.strpath)
    h.commit()

    assert manager().get_service.call_count == 1
    manager().restart.assert_not_called()

    h.remove(p)
    h.commit()

    library = tmpdir.join('library.xml')
    assert library.check(exists=True)
    assert library.read_text('utf-8') == (
        "<?xml version='1.0' encoding='utf-8'?>\n<library/>")

    assert manager().get_service.call_count == 2
    manager().restart.assert_not_called()


def test_catalog_no_remote(tmpdir, settings):
    from ideascube.serveradmin.catalog import Catalog

    settings.CATALOG_CACHE_BASE_DIR = tmpdir.strpath
    c = Catalog()
    assert c.list_remotes() == []
    assert tmpdir.join('remotes').check(dir=True)
    assert tmpdir.join('remotes').listdir() == []


def test_catalog_existing_remote(tmpdir, settings):
    from ideascube.serveradmin.catalog import Catalog

    params = {
        'id': 'foo', 'name': 'Content provided by Foo',
        'url': 'http://foo.fr/catalog.yml'}

    tmpdir.mkdir('remotes').join('foo.yml').write(
        'id: {id}\nname: {name}\nurl: {url}'.format(**params))

    settings.CATALOG_CACHE_BASE_DIR = tmpdir.strpath
    c = Catalog()
    remotes = c.list_remotes()
    assert len(remotes) == 1

    remote = remotes[0]
    assert remote.id == params['id']
    assert remote.name == params['name']
    assert remote.url == params['url']


def test_catalog_add_remotes(tmpdir, settings):
    from ideascube.serveradmin.catalog import Catalog

    settings.CATALOG_CACHE_BASE_DIR = tmpdir.strpath
    c = Catalog()
    c.add_remote('foo', 'Content provided by Foo', 'http://foo.fr/catalog.yml')
    remotes = c.list_remotes()
    assert len(remotes) == 1

    remote = remotes[0]
    assert remote.id == 'foo'
    assert remote.name == 'Content provided by Foo'
    assert remote.url == 'http://foo.fr/catalog.yml'

    c.add_remote('bar', 'Content provided by Bar', 'http://bar.fr/catalog.yml')
    remotes = c.list_remotes()
    assert len(remotes) == 2

    remote = remotes[0]
    assert remote.id == 'bar'
    assert remote.name == 'Content provided by Bar'
    assert remote.url == 'http://bar.fr/catalog.yml'

    remote = remotes[1]
    assert remote.id == 'foo'
    assert remote.name == 'Content provided by Foo'
    assert remote.url == 'http://foo.fr/catalog.yml'

    with pytest.raises(ValueError) as exc:
        c.add_remote('foo', 'Content by Foo', 'http://foo.fr/catalog.yml')

    assert 'foo' in exc.exconly()


def test_catalog_remove_remote(tmpdir, settings):
    from ideascube.serveradmin.catalog import Catalog

    params = {
        'id': 'foo', 'name': 'Content provided by Foo',
        'url': 'http://foo.fr/catalog.yml'}

    tmpdir.mkdir('remotes').join('foo.yml').write(
        'id: {id}\nname: {name}\nurl: {url}'.format(**params))

    settings.CATALOG_CACHE_BASE_DIR = tmpdir.strpath
    c = Catalog()
    c.remove_remote(params['id'])
    remotes = c.list_remotes()
    assert len(remotes) == 0

    with pytest.raises(ValueError) as exc:
        c.remove_remote(params['id'])

    assert params['id'] in exc.exconly()


def test_catalog_update_cache(tmpdir, settings, monkeypatch):
    from ideascube.serveradmin.catalog import Catalog

    monkeypatch.setattr(
        'ideascube.serveradmin.catalog.urlretrieve', fake_urlretrieve)

    remote_catalog_file = tmpdir.mkdir('source').join('catalog.yml')
    remote_catalog_file.write(
        'all:\n  foovideos:\n    name: Videos from Foo')

    settings.CATALOG_CACHE_BASE_DIR = tmpdir.strpath
    c = Catalog()
    assert c._catalog == {'installed': {}, 'available': {}}

    c.add_remote(
        'foo', 'Content from Foo',
        'file://{}'.format(remote_catalog_file.strpath))
    c.update_cache()
    assert c._catalog == {
        'installed': {},
        'available': {'foovideos': {'name': 'Videos from Foo'}}}

    c = Catalog()
    assert c._catalog == {
        'installed': {},
        'available': {'foovideos': {'name': 'Videos from Foo'}}}


def test_catalog_clear_cache(tmpdir, settings, monkeypatch):
    from ideascube.serveradmin.catalog import Catalog

    monkeypatch.setattr(
        'ideascube.serveradmin.catalog.urlretrieve', fake_urlretrieve)

    remote_catalog_file = tmpdir.mkdir('source').join('catalog.yml')
    remote_catalog_file.write(
        'all:\n  foovideos:\n    name: Videos from Foo')

    settings.CATALOG_CACHE_BASE_DIR = tmpdir.strpath
    c = Catalog()
    c.add_remote(
        'foo', 'Content from Foo',
        'file://{}'.format(remote_catalog_file.strpath))
    c.update_cache()
    assert c._catalog != {'installed': {}, 'available': {}}

    c.clear_cache()
    assert c._catalog == {'installed': {}, 'available': {}}


def test_catalog_install_package(tmpdir, settings, testdatadir, mocker):
    from ideascube.serveradmin.catalog import Catalog

    cachedir = tmpdir.mkdir('cache')
    installdir = tmpdir.mkdir('kiwix')
    sourcedir = tmpdir.mkdir('source')

    zippedzim = testdatadir.join('catalog', 'wikipedia.tum-2015-08')
    path = sourcedir.join('wikipedia_tum_all_nopic_2015-08.zim')
    zippedzim.copy(path)

    remote_catalog_file = sourcedir.join('catalog.yml')
    with remote_catalog_file.open(mode='w') as f:
        f.write('all:\n')
        f.write('  wikipedia.tum:\n')
        f.write('    version: 2015-08\n')
        f.write('    size: 200KB\n')
        f.write('    url: file://{}\n'.format(path))
        f.write(
            '    sha256sum: 335d00b53350c63df45486c5433205f068ad90e33c208064b'
            '212c29a30109c54\n')
        f.write('    type: zipped-zim\n')
        f.write('    handler: kiwix\n')

    mocker.patch('ideascube.serveradmin.catalog.SystemManager')
    mocker.patch(
        'ideascube.serveradmin.catalog.urlretrieve',
        side_effect=fake_urlretrieve)

    settings.CATALOG_CACHE_BASE_DIR = cachedir.strpath
    settings.CATALOG_KIWIX_INSTALL_DIR = installdir.strpath

    c = Catalog()
    c.add_remote(
        'foo', 'Content from Foo',
        'file://{}'.format(remote_catalog_file.strpath))
    c.update_cache()
    c.install_packages(['wikipedia.tum'])

    library = installdir.join('library.xml')
    assert library.check(exists=True)

    with library.open(mode='r') as f:
        libdata = f.read()

        assert 'path="data/content/wikipedia.tum.zim"' in libdata
        assert 'indexPath="data/index/wikipedia.tum.zim.idx"' in libdata


def test_catalog_install_package_twice(tmpdir, settings, testdatadir, mocker):
    from ideascube.serveradmin.catalog import Catalog

    cachedir = tmpdir.mkdir('cache')
    installdir = tmpdir.mkdir('kiwix')
    sourcedir = tmpdir.mkdir('source')

    zippedzim = testdatadir.join('catalog', 'wikipedia.tum-2015-08')
    path = sourcedir.join('wikipedia_tum_all_nopic_2015-08.zim')
    zippedzim.copy(path)

    remote_catalog_file = sourcedir.join('catalog.yml')
    with remote_catalog_file.open(mode='w') as f:
        f.write('all:\n')
        f.write('  wikipedia.tum:\n')
        f.write('    version: 2015-08\n')
        f.write('    size: 200KB\n')
        f.write('    url: file://{}\n'.format(path))
        f.write(
            '    sha256sum: 335d00b53350c63df45486c5433205f068ad90e33c208064b'
            '212c29a30109c54\n')
        f.write('    type: zipped-zim\n')
        f.write('    handler: kiwix\n')

    mocker.patch('ideascube.serveradmin.catalog.SystemManager')
    spy_urlretrieve = mocker.patch(
        'ideascube.serveradmin.catalog.urlretrieve',
        side_effect=fake_urlretrieve)

    settings.CATALOG_CACHE_BASE_DIR = cachedir.strpath
    settings.CATALOG_KIWIX_INSTALL_DIR = installdir.strpath

    c = Catalog()
    c.add_remote(
        'foo', 'Content from Foo',
        'file://{}'.format(remote_catalog_file.strpath))
    c.update_cache()
    c.install_packages(['wikipedia.tum'])

    # Once to download the remote catalog.yml, once to download the package
    assert spy_urlretrieve.call_count == 2

    c.install_packages(['wikipedia.tum'])

    assert spy_urlretrieve.call_count == 2


def test_catalog_install_package_already_downloaded(
        tmpdir, settings, testdatadir, mocker):
    from ideascube.serveradmin.catalog import Catalog

    cachedir = tmpdir.mkdir('cache')
    packagesdir = cachedir.mkdir('packages')
    installdir = tmpdir.mkdir('kiwix')
    sourcedir = tmpdir.mkdir('source')

    zippedzim = testdatadir.join('catalog', 'wikipedia.tum-2015-08')
    path = sourcedir.join('wikipedia_tum_all_nopic_2015-08.zim')
    zippedzim.copy(packagesdir.join('wikipedia.tum-2015-08'))

    remote_catalog_file = sourcedir.join('catalog.yml')
    with remote_catalog_file.open(mode='w') as f:
        f.write('all:\n')
        f.write('  wikipedia.tum:\n')
        f.write('    version: 2015-08\n')
        f.write('    size: 200KB\n')
        f.write('    url: file://{}\n'.format(path))
        f.write(
            '    sha256sum: 335d00b53350c63df45486c5433205f068ad90e33c208064b'
            '212c29a30109c54\n')
        f.write('    type: zipped-zim\n')
        f.write('    handler: kiwix\n')

    mocker.patch('ideascube.serveradmin.catalog.SystemManager')
    spy_urlretrieve = mocker.patch(
        'ideascube.serveradmin.catalog.urlretrieve',
        side_effect=fake_urlretrieve)

    settings.CATALOG_CACHE_BASE_DIR = cachedir.strpath
    settings.CATALOG_KIWIX_INSTALL_DIR = installdir.strpath

    c = Catalog()
    c.add_remote(
        'foo', 'Content from Foo',
        'file://{}'.format(remote_catalog_file.strpath))
    c.update_cache()
    c.install_packages(['wikipedia.tum'])

    library = installdir.join('library.xml')
    assert library.check(exists=True)

    with library.open(mode='r') as f:
        libdata = f.read()

        assert 'path="data/content/wikipedia.tum.zim"' in libdata
        assert 'indexPath="data/index/wikipedia.tum.zim.idx"' in libdata

    # Once to download the remote catalog.yml
    assert spy_urlretrieve.call_count == 1


def test_catalog_install_package_partially_downloaded(
        tmpdir, settings, testdatadir, mocker):
    from ideascube.serveradmin.catalog import Catalog

    cachedir = tmpdir.mkdir('cache')
    packagesdir = cachedir.mkdir('packages')
    installdir = tmpdir.mkdir('kiwix')
    sourcedir = tmpdir.mkdir('source')

    zippedzim = testdatadir.join('catalog', 'wikipedia.tum-2015-08')
    path = sourcedir.join('wikipedia_tum_all_nopic_2015-08.zim')
    zippedzim.copy(path)

    # Partially download the package
    packagesdir.join('wikipedia.tum-2015-08').write_binary(
        zippedzim.read_binary()[:100])

    remote_catalog_file = sourcedir.join('catalog.yml')
    with remote_catalog_file.open(mode='w') as f:
        f.write('all:\n')
        f.write('  wikipedia.tum:\n')
        f.write('    version: 2015-08\n')
        f.write('    size: 200KB\n')
        f.write('    url: file://{}\n'.format(path))
        f.write(
            '    sha256sum: 335d00b53350c63df45486c5433205f068ad90e33c208064b'
            '212c29a30109c54\n')
        f.write('    type: zipped-zim\n')
        f.write('    handler: kiwix\n')

    mocker.patch('ideascube.serveradmin.catalog.SystemManager')
    mocker.patch(
        'ideascube.serveradmin.catalog.urlretrieve',
        side_effect=fake_urlretrieve)

    settings.CATALOG_CACHE_BASE_DIR = cachedir.strpath
    settings.CATALOG_KIWIX_INSTALL_DIR = installdir.strpath

    c = Catalog()
    c.add_remote(
        'foo', 'Content from Foo',
        'file://{}'.format(remote_catalog_file.strpath))
    c.update_cache()
    c.install_packages(['wikipedia.tum'])

    library = installdir.join('library.xml')
    assert library.check(exists=True)

    with library.open(mode='r') as f:
        libdata = f.read()

        assert 'path="data/content/wikipedia.tum.zim"' in libdata
        assert 'indexPath="data/index/wikipedia.tum.zim.idx"' in libdata


def test_catalog_install_package_partially_downloaded_but_corrupted(
        tmpdir, settings, testdatadir, mocker):
    from ideascube.serveradmin.catalog import Catalog

    cachedir = tmpdir.mkdir('cache')
    packagesdir = cachedir.mkdir('packages')
    installdir = tmpdir.mkdir('kiwix')
    sourcedir = tmpdir.mkdir('source')

    zippedzim = testdatadir.join('catalog', 'wikipedia.tum-2015-08')
    path = sourcedir.join('wikipedia_tum_all_nopic_2015-08.zim')
    zippedzim.copy(path)

    # Partially download the package
    packagesdir.join('wikipedia.tum-2015-08').write_binary(
        b'corrupt download')

    remote_catalog_file = sourcedir.join('catalog.yml')
    with remote_catalog_file.open(mode='w') as f:
        f.write('all:\n')
        f.write('  wikipedia.tum:\n')
        f.write('    version: 2015-08\n')
        f.write('    size: 200KB\n')
        f.write('    url: file://{}\n'.format(path))
        f.write(
            '    sha256sum: 335d00b53350c63df45486c5433205f068ad90e33c208064b'
            '212c29a30109c54\n')
        f.write('    type: zipped-zim\n')
        f.write('    handler: kiwix\n')

    mocker.patch('ideascube.serveradmin.catalog.SystemManager')
    mocker.patch(
        'ideascube.serveradmin.catalog.urlretrieve',
        side_effect=fake_urlretrieve)

    settings.CATALOG_CACHE_BASE_DIR = cachedir.strpath
    settings.CATALOG_KIWIX_INSTALL_DIR = installdir.strpath

    c = Catalog()
    c.add_remote(
        'foo', 'Content from Foo',
        'file://{}'.format(remote_catalog_file.strpath))
    c.update_cache()
    c.install_packages(['wikipedia.tum'])

    library = installdir.join('library.xml')
    assert library.check(exists=True)

    with library.open(mode='r') as f:
        libdata = f.read()

        assert 'path="data/content/wikipedia.tum.zim"' in libdata
        assert 'indexPath="data/index/wikipedia.tum.zim.idx"' in libdata


def test_catalog_install_package_does_not_exist(
        tmpdir, settings, testdatadir, mocker):
    from ideascube.serveradmin.catalog import Catalog, NoSuchPackage

    cachedir = tmpdir.mkdir('cache')
    sourcedir = tmpdir.mkdir('source')

    zippedzim = testdatadir.join('catalog', 'wikipedia.tum-2015-08')
    path = sourcedir.join('wikipedia_tum_all_nopic_2015-08.zim')
    zippedzim.copy(path)

    remote_catalog_file = sourcedir.join('catalog.yml')
    with remote_catalog_file.open(mode='w') as f:
        f.write('all:\n')
        f.write('  wikipedia.tum:\n')
        f.write('    version: 2015-08\n')
        f.write('    size: 200KB\n')
        f.write('    url: file://{}\n'.format(path))
        f.write(
            '    sha256sum: 335d00b53350c63df45486c5433205f068ad90e33c208064b'
            '212c29a30109c54\n')
        f.write('    type: zipped-zim\n')
        f.write('    handler: kiwix\n')

    mocker.patch('ideascube.serveradmin.catalog.SystemManager')
    mocker.patch(
        'ideascube.serveradmin.catalog.urlretrieve',
        side_effect=fake_urlretrieve)

    settings.CATALOG_CACHE_BASE_DIR = cachedir.strpath

    c = Catalog()
    c.add_remote(
        'foo', 'Content from Foo',
        'file://{}'.format(remote_catalog_file.strpath))
    c.update_cache()

    with pytest.raises(NoSuchPackage):
        c.install_packages(['nosuchpackage'])


def test_catalog_install_package_with_missing_type(
        tmpdir, settings, testdatadir, mocker):
    from ideascube.serveradmin.catalog import Catalog, InvalidPackageMetadata

    cachedir = tmpdir.mkdir('cache')
    sourcedir = tmpdir.mkdir('source')

    zippedzim = testdatadir.join('catalog', 'wikipedia.tum-2015-08')
    path = sourcedir.join('wikipedia_tum_all_nopic_2015-08.zim')
    zippedzim.copy(path)

    remote_catalog_file = sourcedir.join('catalog.yml')
    with remote_catalog_file.open(mode='w') as f:
        f.write('all:\n')
        f.write('  wikipedia.tum:\n')
        f.write('    version: 2015-08\n')
        f.write('    size: 200KB\n')
        f.write('    url: file://{}\n'.format(path))
        f.write(
            '    sha256sum: 335d00b53350c63df45486c5433205f068ad90e33c208064b'
            '212c29a30109c54\n')
        f.write('    handler: kiwix\n')

    mocker.patch(
        'ideascube.serveradmin.catalog.urlretrieve',
        side_effect=fake_urlretrieve)

    settings.CATALOG_CACHE_BASE_DIR = cachedir.strpath

    c = Catalog()
    c.add_remote(
        'foo', 'Content from Foo',
        'file://{}'.format(remote_catalog_file.strpath))
    c.update_cache()

    with pytest.raises(InvalidPackageMetadata):
        c.install_packages(['wikipedia.tum'])


def test_catalog_install_package_with_unknown_type(
        tmpdir, settings, testdatadir, mocker):
    from ideascube.serveradmin.catalog import Catalog, InvalidPackageType

    cachedir = tmpdir.mkdir('cache')
    sourcedir = tmpdir.mkdir('source')

    zippedzim = testdatadir.join('catalog', 'wikipedia.tum-2015-08')
    path = sourcedir.join('wikipedia_tum_all_nopic_2015-08.zim')
    zippedzim.copy(path)

    remote_catalog_file = sourcedir.join('catalog.yml')
    with remote_catalog_file.open(mode='w') as f:
        f.write('all:\n')
        f.write('  wikipedia.tum:\n')
        f.write('    version: 2015-08\n')
        f.write('    size: 200KB\n')
        f.write('    url: file://{}\n'.format(path))
        f.write(
            '    sha256sum: 335d00b53350c63df45486c5433205f068ad90e33c208064b'
            '212c29a30109c54\n')
        f.write('    type: something-not-supported\n')
        f.write('    handler: kiwix\n')

    mocker.patch(
        'ideascube.serveradmin.catalog.urlretrieve',
        side_effect=fake_urlretrieve)

    settings.CATALOG_CACHE_BASE_DIR = cachedir.strpath

    c = Catalog()
    c.add_remote(
        'foo', 'Content from Foo',
        'file://{}'.format(remote_catalog_file.strpath))
    c.update_cache()

    with pytest.raises(InvalidPackageType):
        c.install_packages(['wikipedia.tum'])


def test_catalog_install_package_with_missing_handler(
        tmpdir, settings, testdatadir, mocker):
    from ideascube.serveradmin.catalog import Catalog, InvalidPackageMetadata

    cachedir = tmpdir.mkdir('cache')
    sourcedir = tmpdir.mkdir('source')

    zippedzim = testdatadir.join('catalog', 'wikipedia.tum-2015-08')
    path = sourcedir.join('wikipedia_tum_all_nopic_2015-08.zim')
    zippedzim.copy(path)

    remote_catalog_file = sourcedir.join('catalog.yml')
    with remote_catalog_file.open(mode='w') as f:
        f.write('all:\n')
        f.write('  wikipedia.tum:\n')
        f.write('    version: 2015-08\n')
        f.write('    size: 200KB\n')
        f.write('    url: file://{}\n'.format(path))
        f.write(
            '    sha256sum: 335d00b53350c63df45486c5433205f068ad90e33c208064b'
            '212c29a30109c54\n')
        f.write('    type: zipped-zim\n')

    mocker.patch(
        'ideascube.serveradmin.catalog.urlretrieve',
        side_effect=fake_urlretrieve)

    settings.CATALOG_CACHE_BASE_DIR = cachedir.strpath

    c = Catalog()
    c.add_remote(
        'foo', 'Content from Foo',
        'file://{}'.format(remote_catalog_file.strpath))
    c.update_cache()

    with pytest.raises(InvalidPackageMetadata):
        c.install_packages(['wikipedia.tum'])


def test_catalog_install_package_with_unknown_handler(
        tmpdir, settings, testdatadir, mocker):
    from ideascube.serveradmin.catalog import Catalog, InvalidHandlerType

    cachedir = tmpdir.mkdir('cache')
    sourcedir = tmpdir.mkdir('source')

    zippedzim = testdatadir.join('catalog', 'wikipedia.tum-2015-08')
    path = sourcedir.join('wikipedia_tum_all_nopic_2015-08.zim')
    zippedzim.copy(path)

    remote_catalog_file = sourcedir.join('catalog.yml')
    with remote_catalog_file.open(mode='w') as f:
        f.write('all:\n')
        f.write('  wikipedia.tum:\n')
        f.write('    version: 2015-08\n')
        f.write('    size: 200KB\n')
        f.write('    url: file://{}\n'.format(path))
        f.write(
            '    sha256sum: 335d00b53350c63df45486c5433205f068ad90e33c208064b'
            '212c29a30109c54\n')
        f.write('    type: zipped-zim\n')
        f.write('    handler: something-not-supported\n')

    mocker.patch(
        'ideascube.serveradmin.catalog.urlretrieve',
        side_effect=fake_urlretrieve)

    settings.CATALOG_CACHE_BASE_DIR = cachedir.strpath

    c = Catalog()
    c.add_remote(
        'foo', 'Content from Foo',
        'file://{}'.format(remote_catalog_file.strpath))
    c.update_cache()

    with pytest.raises(InvalidHandlerType):
        c.install_packages(['wikipedia.tum'])


def test_catalog_remove_package(tmpdir, settings, testdatadir, mocker):
    from ideascube.serveradmin.catalog import Catalog

    cachedir = tmpdir.mkdir('cache')
    installdir = tmpdir.mkdir('kiwix')
    sourcedir = tmpdir.mkdir('source')

    zippedzim = testdatadir.join('catalog', 'wikipedia.tum-2015-08')
    path = sourcedir.join('wikipedia_tum_all_nopic_2015-08.zim')
    zippedzim.copy(path)

    remote_catalog_file = sourcedir.join('catalog.yml')
    with remote_catalog_file.open(mode='w') as f:
        f.write('all:\n')
        f.write('  wikipedia.tum:\n')
        f.write('    version: 2015-08\n')
        f.write('    size: 200KB\n')
        f.write('    url: file://{}\n'.format(path))
        f.write(
            '    sha256sum: 335d00b53350c63df45486c5433205f068ad90e33c208064b'
            '212c29a30109c54\n')
        f.write('    type: zipped-zim\n')
        f.write('    handler: kiwix\n')

    mocker.patch('ideascube.serveradmin.catalog.SystemManager')
    mocker.patch(
        'ideascube.serveradmin.catalog.urlretrieve',
        side_effect=fake_urlretrieve)

    settings.CATALOG_CACHE_BASE_DIR = cachedir.strpath
    settings.CATALOG_KIWIX_INSTALL_DIR = installdir.strpath

    c = Catalog()
    c.add_remote(
        'foo', 'Content from Foo',
        'file://{}'.format(remote_catalog_file.strpath))
    c.update_cache()
    c.install_packages(['wikipedia.tum'])
    c.remove_packages(['wikipedia.tum'])

    library = installdir.join('library.xml')
    assert library.check(exists=True)
    assert library.read_text('utf-8') == (
        "<?xml version='1.0' encoding='utf-8'?>\n<library/>")


def test_catalog_update_package(tmpdir, settings, testdatadir, mocker):
    from ideascube.serveradmin.catalog import Catalog

    cachedir = tmpdir.mkdir('cache')
    installdir = tmpdir.mkdir('kiwix')
    sourcedir = tmpdir.mkdir('source')

    zippedzim = testdatadir.join('catalog', 'wikipedia.tum-2015-08')
    path = sourcedir.join('wikipedia_tum_all_nopic_2015-08.zim')
    zippedzim.copy(path)

    remote_catalog_file = sourcedir.join('catalog.yml')
    with remote_catalog_file.open(mode='w') as f:
        f.write('all:\n')
        f.write('  wikipedia.tum:\n')
        f.write('    version: 2015-08\n')
        f.write('    size: 200KB\n')
        f.write('    url: file://{}\n'.format(path))
        f.write(
            '    sha256sum: 335d00b53350c63df45486c5433205f068ad90e33c208064b'
            '212c29a30109c54\n')
        f.write('    type: zipped-zim\n')
        f.write('    handler: kiwix\n')

    mocker.patch('ideascube.serveradmin.catalog.SystemManager')
    mocker.patch(
        'ideascube.serveradmin.catalog.urlretrieve',
        side_effect=fake_urlretrieve)

    settings.CATALOG_CACHE_BASE_DIR = cachedir.strpath
    settings.CATALOG_KIWIX_INSTALL_DIR = installdir.strpath

    c = Catalog()
    c.add_remote(
        'foo', 'Content from Foo',
        'file://{}'.format(remote_catalog_file.strpath))
    c.update_cache()
    c.install_packages(['wikipedia.tum'])

    library = installdir.join('library.xml')
    assert library.check(exists=True)

    with library.open(mode='r') as f:
        libdata = f.read()

        assert 'path="data/content/wikipedia.tum.zim"' in libdata
        assert 'indexPath="data/index/wikipedia.tum.zim.idx"' in libdata
        assert 'date="2015-08-10"' in libdata

    zippedzim = testdatadir.join('catalog', 'wikipedia.tum-2015-09')
    path = sourcedir.join('wikipedia_tum_all_nopic_2015-09.zim')
    zippedzim.copy(path)

    remote_catalog_file = sourcedir.join('catalog.yml')
    with remote_catalog_file.open(mode='w') as f:
        f.write('all:\n')
        f.write('  wikipedia.tum:\n')
        f.write('    version: 2015-09\n')
        f.write('    size: 200KB\n')
        f.write('    url: file://{}\n'.format(path))
        f.write(
            '    sha256sum: f8794e3c8676258b0b594ad6e464177dda8d66dbcbb04b301'
            'd78fd4c9cf2c3dd\n')
        f.write('    type: zipped-zim\n')
        f.write('    handler: kiwix\n')

    c.update_cache()
    c.upgrade_packages(['wikipedia.tum'])

    library = installdir.join('library.xml')
    assert library.check(exists=True)

    with library.open(mode='r') as f:
        libdata = f.read()

        assert 'path="data/content/wikipedia.tum.zim"' in libdata
        assert 'indexPath="data/index/wikipedia.tum.zim.idx"' in libdata
        assert 'date="2015-09-10"' in libdata


def test_catalog_update_package_already_latest(
        tmpdir, settings, testdatadir, mocker, capsys):
    from ideascube.serveradmin.catalog import Catalog

    cachedir = tmpdir.mkdir('cache')
    installdir = tmpdir.mkdir('kiwix')
    sourcedir = tmpdir.mkdir('source')

    zippedzim = testdatadir.join('catalog', 'wikipedia.tum-2015-08')
    path = sourcedir.join('wikipedia_tum_all_nopic_2015-08.zim')
    zippedzim.copy(path)

    remote_catalog_file = sourcedir.join('catalog.yml')
    with remote_catalog_file.open(mode='w') as f:
        f.write('all:\n')
        f.write('  wikipedia.tum:\n')
        f.write('    version: 2015-08\n')
        f.write('    size: 200KB\n')
        f.write('    url: file://{}\n'.format(path))
        f.write(
            '    sha256sum: 335d00b53350c63df45486c5433205f068ad90e33c208064b'
            '212c29a30109c54\n')
        f.write('    type: zipped-zim\n')
        f.write('    handler: kiwix\n')

    mocker.patch('ideascube.serveradmin.catalog.SystemManager')
    mocker.patch(
        'ideascube.serveradmin.catalog.urlretrieve',
        side_effect=fake_urlretrieve)

    settings.CATALOG_CACHE_BASE_DIR = cachedir.strpath
    settings.CATALOG_KIWIX_INSTALL_DIR = installdir.strpath

    c = Catalog()
    c.add_remote(
        'foo', 'Content from Foo',
        'file://{}'.format(remote_catalog_file.strpath))
    c.update_cache()
    c.install_packages(['wikipedia.tum'])

    library = installdir.join('library.xml')
    assert library.check(exists=True)

    old_mtime = library.mtime()

    # Drop what was logged so far
    capsys.readouterr()

    c.upgrade_packages(['wikipedia.tum'])

    assert library.mtime() == old_mtime

    out, err = capsys.readouterr()
    assert out.strip() == ''
    assert err.strip() == 'wikipedia.tum has no update available'

from ..bbot_fixtures import *


@pytest.mark.asyncio
async def test_http_helpers(bbot_scanner, bbot_config, bbot_httpserver):
    scan1 = bbot_scanner("8.8.8.8", config=bbot_config)
    scan2 = bbot_scanner("127.0.0.1", config=bbot_config)

    user_agent = bbot_config.get("user_agent", "")
    headers = {"User-Agent": user_agent}
    custom_headers = bbot_config.get("http_headers", {})
    headers.update(custom_headers)
    assert headers["test"] == "header"

    url = bbot_httpserver.url_for("/test_http_helpers")
    # test user agent + custom headers
    bbot_httpserver.expect_request(uri="/test_http_helpers", headers=headers).respond_with_data(
        "test_http_helpers_yep"
    )
    response = await scan1.helpers.request(url)
    # should fail because URL is not in-scope
    assert response.status_code == 500
    response = await scan2.helpers.request(url)
    # should suceed because URL is in-scope
    assert response.status_code == 200
    assert response.text == "test_http_helpers_yep"

    # download file
    path = "/test_http_helpers_download"
    url = bbot_httpserver.url_for(path)
    download_content = "test_http_helpers_download_yep"
    bbot_httpserver.expect_request(uri=path).respond_with_data(download_content)
    filename = await scan1.helpers.download(url)
    assert Path(str(filename)).is_file()
    assert scan1.helpers.is_cached(url)
    with open(filename) as f:
        assert f.read() == download_content
    # 404
    path = "/test_http_helpers_download_404"
    url = bbot_httpserver.url_for(path)
    download_content = "404"
    bbot_httpserver.expect_request(uri=path).respond_with_data(download_content, status=404)
    filename = await scan1.helpers.download(url)
    assert filename is None
    assert not scan1.helpers.is_cached(url)

    # wordlist
    path = "/test_http_helpers_wordlist"
    url = bbot_httpserver.url_for(path)
    download_content = "a\ncool\nword\nlist"
    bbot_httpserver.expect_request(uri=path).respond_with_data(download_content)
    filename = await scan1.helpers.wordlist(url)
    assert Path(str(filename)).is_file()
    assert scan1.helpers.is_cached(url)
    assert list(scan1.helpers.read_file(filename)) == ["a", "cool", "word", "list"]

    # page iteration
    base_path = "/test_http_page_iteration"
    template_path = base_path + "/{page}?page_size={page_size}&offset={offset}"
    template_url = bbot_httpserver.url_for(template_path)
    bbot_httpserver.expect_request(
        uri=f"{base_path}/1", query_string={"page_size": "100", "offset": "0"}
    ).respond_with_data("page1")
    bbot_httpserver.expect_request(
        uri=f"{base_path}/2", query_string={"page_size": "100", "offset": "100"}
    ).respond_with_data("page2")
    bbot_httpserver.expect_request(
        uri=f"{base_path}/3", query_string={"page_size": "100", "offset": "200"}
    ).respond_with_data("page3")
    results = []
    agen = scan1.helpers.api_page_iter(template_url)
    try:
        async for result in agen:
            if result and result.text.startswith("page"):
                results.append(result)
            else:
                break
    finally:
        await agen.aclose()
    assert not results
    agen = scan1.helpers.api_page_iter(template_url, json=False)
    try:
        async for result in agen:
            if result and result.text.startswith("page"):
                results.append(result)
            else:
                break
    finally:
        await agen.aclose()
    assert [r.text for r in results] == ["page1", "page2", "page3"]


@pytest.mark.asyncio
async def test_http_interactsh(bbot_scanner, bbot_config, bbot_httpserver):
    from bbot.core.helpers.interactsh import server_list

    scan1 = bbot_scanner("8.8.8.8", config=bbot_config)

    interactsh_client = scan1.helpers.interactsh()

    async def async_callback(data):
        log.debug(f"interactsh poll: {data}")

    interactsh_domain = await interactsh_client.register(callback=async_callback)
    assert any(interactsh_domain.endswith(f"{s}") for s in server_list)
    data_list = await interactsh_client.poll()
    assert isinstance(data_list, list)
    assert await interactsh_client.deregister() is None

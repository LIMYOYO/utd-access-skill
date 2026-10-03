import asyncio
import httpx
import pytest
from paper_access.collect import collect


class Pages:
    def __init__(self, fail=False):
        self.calls=[];self.fail=fail
    async def request(self, method,url,**kwargs):
        assert "sort" not in kwargs["params"]  # Crossref rejects published sorting with cursors.
        cursor=kwargs["params"]["cursor"];self.calls.append(cursor)
        if cursor=="next" and self.fail:raise OSError("interrupted")
        ids=["10.1234/a","10.1234/b"] if cursor=="*" else ["10.1234/b","10.1234/c"]
        if cursor=="end":ids=[]
        return httpx.Response(200,json={"message":{"next-cursor":"next" if cursor=="*" else "end","items":[{"DOI":doi,"title":[doi]} for doi in ids]}})


def test_collect_resumes_saved_cursor_and_deduplicates(tmp_path):
    out=tmp_path/"papers.csv"
    first=Pages(fail=True)
    with pytest.raises(OSError):asyncio.run(collect(first,issn="0025-1909",from_year=2020,to_year=2026,max_records=4,output=out,page_size=2))
    second=Pages()
    result=asyncio.run(collect(second,issn="0025-1909",from_year=2020,to_year=2026,max_records=4,output=out,page_size=2))
    assert second.calls==["next","end"]
    assert result["count"]==3 and result["exhausted"]
    assert out.read_text().count("10.1234/a")==2  # identifier and fixture title
    with pytest.raises(ValueError):asyncio.run(collect(second,issn="0025-1909",from_year=2021,to_year=2026,max_records=4,output=out,page_size=2))


def test_same_collection_rejects_concurrent_executor(tmp_path):
    class Blocking(Pages):
        async def request(self,*args,**kwargs):
            entered.set()
            await release.wait()
            return await super().request(*args,**kwargs)
    async def run():
        global entered,release
        entered=asyncio.Event();release=asyncio.Event()
        args=dict(issn="0025-1909",from_year=2020,to_year=2026,max_records=2,output=tmp_path/"out.csv",page_size=2)
        first=asyncio.create_task(collect(Blocking(),**args))
        await entered.wait()
        with pytest.raises(ValueError,match="active executor"):
            await collect(Pages(),**args)
        release.set()
        await first
    asyncio.run(run())

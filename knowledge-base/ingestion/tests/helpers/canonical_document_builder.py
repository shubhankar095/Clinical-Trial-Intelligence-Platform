import copy

def expand_canonical_payload(payload: dict, *, copies: int) -> dict:
    if copies < 1:
        raise ValueError("copies must be positive")
    result = copy.deepcopy(payload)
    original = payload["pages"]
    pages=[]; parts=[]; offset=0
    for repetition in range(copies):
        for source in original:
            text=source["text"]
            page=copy.deepcopy(source)
            page["page_number"]=len(pages)+1
            page["start_offset"]=offset
            page["end_offset"]=offset+len(text)
            pages.append(page); parts.append(text); offset+=len(text)
    result["raw_text"]="".join(parts)
    result["pages"]=pages
    result["page_count"]=len(pages)
    result["ocr_page_count"]=sum(1 for p in pages if p["ocr_applied"])
    result["images"]=[]; result["image_count"]=0
    result["tables"]=[]; result["table_count"]=0
    return result

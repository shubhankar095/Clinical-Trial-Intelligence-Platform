from services.document_processing_service import DocumentProcessingService
from dataclasses import asdict

def main():

    service = DocumentProcessingService()

    document = service.process_document(
        bucket_name="clinical-kb",
        #object_key="protocols/ONC101/protocol.pdf",
        object_key="Shubhankar_resume_pdf.pdf",
        s3_metadata={
            "study_id": "ONC101",
            "document_type": "PROTOCOL",
            "version": "3"
        }
    )

    #print(document)
    return document


if __name__ == "__main__":
    document =main()

    document_dict = asdict(document)

    for key, value in document_dict.items():

        if key == "raw_text":
            print(f" - {key} : {len(value)}")
        elif key in ["chunks","pages"]:
            print(f" - {key} : ")
            for page in value:
                for k,v in page.items():
                    if k == "text":
                        print(f"   - {k} : {len(v)}")
                    elif k =="embedding":
                        print(f"   - {k} : {len(v)}")
                    else:
                        print(f"   - {k} : {v}")
                print()    
        else:   
            print(f" - {key} : {value}")


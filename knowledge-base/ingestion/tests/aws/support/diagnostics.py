from __future__ import annotations
from .polling import queue_counts, service_counts, find_registry_record

def snapshot(deployment, document_id=None):
    result={"ecs":service_counts(deployment),"queue":queue_counts(deployment,deployment.queue_url),"dlq":queue_counts(deployment,deployment.dlq_url)}
    if document_id: result["registry"]=find_registry_record(deployment,document_id)
    return result

########################################################################

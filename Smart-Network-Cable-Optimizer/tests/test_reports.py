import io
import zipfile

import pandas as pd
import pytest

from modules import network_service as ns
from modules import report_generator as rg


@pytest.fixture
def parts(sample_db):
    g = ns.load_graph(sample_db)
    r = ns.run_algorithm(g, ns.PRIM, record_steps=False)
    return g, r, ns.cost_metrics(g, r)


def test_pdf_is_valid_and_nonempty(parts):
    pdf = rg.build_pdf_report(*parts)
    assert pdf.startswith(b"%PDF") and pdf.rstrip().endswith(b"%%EOF") and len(pdf) > 5000


def test_pdf_for_disconnected_network(sample_db):
    from database import db
    for c in db.get_connections(db_path=sample_db):
        if 6 in (c["source_id"], c["dest_id"]):
            db.delete_connection(c["id"], sample_db)
    g = ns.load_graph(sample_db)
    r = ns.run_algorithm(g)
    assert rg.build_pdf_report(g, r, ns.cost_metrics(g, r)).startswith(b"%PDF")


def test_csv_exports(parts):
    files = rg.build_csv_exports(*parts)
    assert set(files) == {"buildings.csv", "cable_connections.csv", "mst_results.csv", "cost_analysis.csv", "cost_by_cable_type.csv"}
    mst = pd.read_csv(io.BytesIO(files["mst_results.csv"]))
    assert len(mst) == 5 and mst["Total Cost"].sum() == 13000
    assert len(pd.read_csv(io.BytesIO(files["buildings.csv"]))) == 6
    cost = dict(pd.read_csv(io.BytesIO(files["cost_analysis.csv"])).values)
    assert float(cost["Savings"]) == 28000
    with zipfile.ZipFile(io.BytesIO(rg.zip_csvs(files))) as z:
        assert len(z.namelist()) == 5

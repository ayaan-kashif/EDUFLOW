from app.api.ingestion import safe_upload_filename


def test_safe_upload_filename_keeps_plain_basename():
    assert safe_upload_filename("syllabus.pdf") == "syllabus.pdf"


def test_safe_upload_filename_handles_missing_name():
    assert safe_upload_filename(None) == "upload"
    assert safe_upload_filename("") == "upload"


def test_safe_upload_filename_strips_posix_paths():
    assert safe_upload_filename("../../outside.pdf") == "outside.pdf"


def test_safe_upload_filename_strips_windows_paths():
    assert safe_upload_filename(r"..\..\outside.pdf") == "outside.pdf"

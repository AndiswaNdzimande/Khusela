__test__ = False  # Prevent pytest from collecting this CLI demonstration script
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from forensics import analyze_document_forensics
except ImportError:
    from ocr.forensics import analyze_document_forensics
except ImportError:
    from forensics import analyze_document_forensics

def inspect_pdf_sample(file_path):
    print(f"\n{'='*50}")
    print(f"🔍 Analyzing: {file_path}")
    print(f"{'='*50}")
    
    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()
            
        # Run the forensic engine
        # is_pdf=True forces it to run the PDF-specific checks
        results = analyze_document_forensics(file_bytes, ocr_text=None, is_pdf=True)
        
        # Print the results nicely
        print(f"Status: {results['severity']}")
        print(f"Tampered: {results['tampering_detected']}")
        print(f"Summary: {results['summary']}")
        print(f"Reasons: {results['reasons']}")
        
        if results['pdf_forensics']:
            print("\n--- PDF Stream Forensics ---")
            print(f"White boxes found: {results['pdf_forensics']['white_boxes_found']}")
            print(f"Font subsets: {results['pdf_forensics']['font_subsets']}")
            
        if results['metadata']:
            print("\n--- Metadata ---")
            print(f"Producer: {results['metadata']['producer']}")
            print(f"Suspicious Software: {results['metadata']['software']}")

    except FileNotFoundError:
        print(f"[-] File not found: {file_path}. Make sure you ran the generator script first!")
    except Exception as e:
        print(f"[-] Error running test: {e}")

if __name__ == "__main__":
    # Test the files we generated in the previous steps
    # Make sure these files exist in the same folder!
    inspect_pdf_sample("PaymentNotification.pdf")
    inspect_pdf_sample("tampered_standard_bank.pdf")
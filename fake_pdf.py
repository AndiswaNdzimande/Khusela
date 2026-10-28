import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from pypdf import PdfReader, PdfWriter
import io

def create_standard_bank_letter(filename: str, account_number: str, date_opened: str):
    """Generates a realistic-looking Standard Bank Confirmation Letter."""
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    
    # 1. Header & Logo
    # Using the blue logo you provided
    logo_path = "standard_bank_logo.png"
    if os.path.exists(logo_path):
        # Place logo top right
        c.drawImage(logo_path, width - 200, height - 80, width=130, height=60, preserveAspectRatio=True, mask='auto')
    else:
        print("[!] Warning: standard_bank_logo.png not found. Using text placeholder.")
        c.setFillColor(HexColor("#0033A1")) # Standard Bank Blue
        c.setFont("Helvetica-Bold", 24)
        c.drawRightString(width - 50, height - 60, "Standard Bank")
        c.setFillColor(HexColor("#000000"))

    # 2. Top Header (Date/Time stamp)
    c.setFont("Helvetica", 9)
    c.drawString(50, height - 50, "2021- 10- 26 01- 43- 42")
    
    # 3. Date and Salutation
    c.setFont("Helvetica", 11)
    c.drawString(50, height - 90, "Date 26 October 2021")
    
    c.drawString(50, height - 120, "To Whom It May Concern")
    
    # 4. Subject Line
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 150, "Re: Confirmation of Bank account")
    
    # 5. Body Paragraph
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 180, "This letter serves to confirm that the below mentioned customer holds the below Standard Bank account.")
    
    # 6. Customer Details (The core data block)
    # The original uses a dense layout. We will replicate this structure.
    start_y = height - 220
    line_height = 22
    
    fields = [
        ("Legal entity name", "VALLEY ELECTRICAL CONTRACTORS PTY LTD"),
        ("Name of accountholder", "VALLEY ELECTRICAL CONTRACTORS PTY LTD"),
        ("Registration/Identity/Passport number", "2015/104111/07"),
        ("Account number", account_number),
        ("Account type", "BUSINESS CURRENT ACCOUNT"),
        ("Branch", "MILNETON"),
        ("Branch code", "026509"),
        ("Branch code (electronic payments)", "051001"),
        ("SWIFT address", "SBZA ZA JJ"),
        ("Date account opened", date_opened)
    ]
    
    for label, value in fields:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, start_y, label)
        c.setFont("Helvetica", 10)
        c.drawString(260, start_y, value)
        start_y -= line_height
        
    # 7. Closing Paragraph
    start_y -= 10
    c.setFont("Helvetica", 10)
    c.drawString(50, start_y, "This letter or your reliance on same does not give rise to any obligations or liability on the part of the Bank and/or its officials.")
    
    start_y -= 20
    c.drawString(50, start_y, "We trust the above meets with your requirements.")
    
    # 8. Sign-off
    start_y -= 30
    c.drawString(50, start_y, "Yours sincerely")
    
    start_y -= 40
    c.drawString(50, start_y, "CLARESA PRETORIUS")
    start_y -= 15
    c.drawString(50, start_y, "CONSULTANT BUSINESS BANKING")
    start_y -= 15
    c.drawString(50, start_y, "0214012420")
    
    # 9. Disclaimer
    start_y -= 30
    c.setFont("Helvetica", 8)
    disclaimer = (
        "Disclaimer Whilst care has been taken in compiling this letter, Standard Bank makes no representations or warrant "
        "(expressed or implied) about the accuracy, or completeness of the information contained herein for any purpose. "
        "Standard Bank, its employees or agents accept no liability to any part for any loss, damage or costs however arising, "
        "whether directly or indirectly arising from any action or decision taken as a result of any person relying on or "
        "otherwise using this document or arising from any omission from it."
    )
    
    # Wrap the disclaimer text manually
    words = disclaimer.split()
    line = ""
    for word in words:
        if c.stringWidth(line + " " + word, "Helvetica", 8) < (width - 100):
            line += word + " "
        else:
            c.drawString(50, start_y, line)
            start_y -= 10
            line = word + " "
    c.drawString(50, start_y, line)
    
    # 10. Footer (Very small text)
    footer_y = 60
    c.setFont("Helvetica", 6)
    c.drawString(50, footer_y, "Standard Bank Centre 1st Floor 5 Slimmonds Street Johannesburg 2001 / PO Box 61690 Marshalltown 2107 South Africa")
    c.drawString(50, footer_y - 8, "Tel. Switchboard: +27 (0)11 636 9112 Fax +27 (0)11 636 4207 / Name.Surname@standardbank.co.za / standardbank.co.za")
    c.drawString(50, footer_y - 16, "The Standard Bank of South Africa Limited (Reg.No. 1962/000738/06) Authorised financial services and registered credit provider (NCRCP15)")
    
    # 11. Directors (Tiny text)
    c.setFont("Helvetica", 5)
    directors_text = "Directors: TS Gcabashe (Chairman) L Fuzile (Chief Executive) PLH Cook A Daelmke MA Erasmus' GJ Fraser- Moleketi Xueqing Guan' GMB Kenney JH Maree NNA Matyumza KD Moroka NMC Nyembzi ML Otour- Olteno' ANA Peterside CON' MJD Ruck SK Tshabalala JM Vice Lubin Wang'"
    
    words = directors_text.split()
    line = ""
    current_y = footer_y - 30
    for word in words:
        if c.stringWidth(line + " " + word, "Helvetica", 5) < (width - 100):
            line += word + " "
        else:
            c.drawString(50, current_y, line)
            current_y -= 6
            line = word + " "
    c.drawString(50, current_y, line)
    
    c.drawString(50, current_y - 10, "Company Secretary: Z Stephen 26/05/2021")
    
    c.save()

def tamper_pdf_account_number(original_pdf_path: str, output_pdf_path: str, new_account_number: str):
    """
    Simulates a real-world PDF tampering attack.
    Overlays a new account number on top of the original one.
    """
    reader = PdfReader(original_pdf_path)
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)
        
    page = writer.pages[0]
    
    # Create a new overlay page
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=A4)
    
    # Coordinates based on the layout above
    # The Account Number is the 4th field. 
    # Start Y = height - 220. Line height = 22. 
    # Y = height - 220 - (3 * 22) = height - 286
    
    target_y = A4[1] - 286
    target_x = 260
    
    # Draw a white box to cover the old account number
    # Width is estimated based on the length of the old number
    c.setFillColor(HexColor("#FFFFFF"))
    c.rect(target_x - 2, target_y - 3, 100, 14, fill=1, stroke=0) 
    
    # Draw the new fake account number
    c.setFillColor(HexColor("#000000"))
    c.setFont("Helvetica", 10) # Match the original font exactly
    c.drawString(target_x, target_y, new_account_number)
    c.save()
    
    packet.seek(0)
    overlay_reader = PdfReader(packet)
    overlay_page = overlay_reader.pages[0]
    
    # Merge the overlay onto the original page
    page.merge_page(overlay_page)
    
    with open(output_pdf_path, "wb") as f:
        writer.write(f)
        
    print(f"[+] Generated Tampered PDF: {output_pdf_path}")

if __name__ == "__main__":
    clean_file = "clean_standard_bank.pdf"
    tampered_file = "tampered_standard_bank.pdf"
    
    # 1. Create the clean, authentic-looking PDF
    # Using the exact details from the document you provided
    create_standard_bank_letter(
        clean_file, 
        account_number="271291478", 
        date_opened="08 October 2008"
    )
    print(f"[+] Generated Clean PDF: {clean_file}")

    # 2. Create the tampered PDF
    # Changing the account number to something else to simulate fraud
    tamper_pdf_account_number(
        clean_file, 
        tampered_file, 
        new_account_number="998877665" 
    )
import os
import pypdf  

class PolicyReader:
    def __init__(self):
        self.last_extraction = {}

    def get_policy_context(self, pdf_path):
        """
        Extracts text while preserving 1-indexed page numbers for AI citation.
        Returns a dictionary: {page_number: "text_content"}
        """
        if not os.path.exists(pdf_path):
            return {"error": f"Policy file not found: {pdf_path}"}

        page_map = {}
        try:
            reader = pypdf.PdfReader(pdf_path)
            for i, page in enumerate(reader.pages):
                content = page.extract_text()
                if content:
                    
                    page_map[i + 1] = content.strip()
            
            if not page_map:
                return {"error": "PDF contains no extractable text (check if scanned image)."}
            
            self.last_extraction = page_map
            return page_map

        except Exception as e:
            return {"error": f"Failed to parse PDF: {str(e)}"}

    def get_prompt_ready_text(self, pdf_path):
        """
        Formats the PDF content into a structure the AI can explicitly cite.
        Wraps content in clear delimiters for the Discovery Agent's Auditor prompt.
        """
        data = self.get_policy_context(pdf_path)
        if "error" in data:
            return data["error"]
        
        formatted_text = "--- POLICY DOCUMENT START ---\n"
        for page_num, text in data.items():
            formatted_text += f"[PAGE {page_num}]\n{text}\n\n"
        formatted_text += "--- POLICY DOCUMENT END ---"
        
        return formatted_text
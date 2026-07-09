from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from docx import Document
from jinja2 import Environment, FileSystemLoader, select_autoescape
class DocumentGenerator:
    def __init__(self, templates_dir: str = "templates"):
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(exist_ok=True)
        
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render Jinja2 template to string"""
        template = self.jinja_env.get_template(template_name)
        return template.render(**context)

    def generate_claim(self, data: Dict[str, Any]) -> Path:
        """Generate исковое заявление"""
        context = self._prepare_claim_context(data)
        content = self.render_template("claim.j2", context)
        doc = Document()
        self._apply_formatting(doc, content)
        output_path = Path("generated") / f"iskovoe_zayavlenie_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
        output_path.parent.mkdir(exist_ok=True)
        doc.save(output_path)
        return output_path

import asyncio
from typing import List

from jinja2 import Environment, FileSystemLoader, select_autoescape

from substitution_plan.storage import SubstitutionDay


class Templates:
    def __init__(self, base_path=""):
        self._jinja_env = Environment(
            loader=FileSystemLoader("website/templates/"),
            autoescape=select_autoescape(["html"]),
            enable_async=True,
            trim_blocks=True,
            lstrip_blocks=True
        )
        self.base_path = base_path
        # static
        self._template_about = self._jinja_env.get_template("about.html")
        self._template_error_404 = self._jinja_env.get_template("error-404.html")
        self._template_error_500_students = self._jinja_env.get_template("error-500-students.html")
        self._template_error_500_teachers = self._jinja_env.get_template("error-500-teachers.html")
        self._template_privacy = self._jinja_env.get_template("privacy.html")

        # non-static
        self._template_substitution_plan_students = self._jinja_env.get_template("substitution-plan-students.html")
        self._template_substitution_plan_teachers = self._jinja_env.get_template("substitution-plan-teachers.html")

    async def render_about(self):
        return await self._template_about.render_async(base_path=self.base_path)

    async def render_error_404(self):
        return await self._template_error_404.render_async(base_path=self.base_path)

    async def render_error_500_students(self):
        return await self._template_error_500_students.render_async(base_path=self.base_path)

    async def render_error_500_teachers(self):
        return await self._template_error_500_teachers.render_async(base_path=self.base_path)

    async def render_privacy(self):
        return await self._template_privacy.render_async(base_path=self.base_path)

    async def render_substitution_plan_students(self, status: str, days: List[SubstitutionDay], selection=None,
                                                selection_str: str = None):
        return await self._template_substitution_plan_students.render_async(base_path=self.base_path,
                                                                            status=status, days=days,
                                                                            selection=selection,
                                                                            selection_str=selection_str)

    async def render_substitution_plan_teachers(self, status: str, days: List[SubstitutionDay], selection=None,
                                                selection_str: str = None):
        return await self._template_substitution_plan_teachers.render_async(base_path=self.base_path,
                                                                            status=status, days=days,
                                                                            selection=selection,
                                                                            selection_str=selection_str)

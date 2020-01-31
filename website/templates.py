import asyncio
from typing import List

from jinja2 import Environment, FileSystemLoader, select_autoescape

from substitution_plan.storage import SubstitutionDay


class Templates:
    def __init__(self):
        self._jinja_env = Environment(
            loader=FileSystemLoader("website/templates/"),
            autoescape=select_autoescape(["html"]),
            enable_async=True
        )
        # static
        self._template_about = self._jinja_env.get_template("about.html")
        self._template_error_404 = self._jinja_env.get_template("error-404.html")
        self._template_error_500_students = self._jinja_env.get_template("error-500-students.html")
        self._template_error_500_teachers = self._jinja_env.get_template("error-500-teachers.html")
        self._template_privacy = self._jinja_env.get_template("privacy.html")
        self.about = None
        self.error_404 = None
        self.error_500_students = None
        self.error_500_teachers = None
        self.privacy = None

        # non-static
        self._template_substitution_plan_students = self._jinja_env.get_template("substitution-plan-students.html")
        self._template_substitution_plan_teachers = self._jinja_env.get_template("substitution-plan-teachers.html")

    async def load_static(self):
        self.about, self.error_404, self.error_500_students, self.error_500_teachers, self.privacy = \
            await asyncio.gather(
                self._template_about.render_async(),
                self._template_error_404.render_async(),
                self._template_error_500_students.render_async(),
                self._template_error_500_teachers.render_async(),
                self._template_privacy.render_async()
            )

    async def render_substitution_plan_students(self, status: str, days: List[SubstitutionDay]):
        return await self._template_substitution_plan_students.render_async(status=status, days=days)

    async def render_substitution_plan_teachers(self, status: str, days: List[SubstitutionDay]):
        return await self._template_substitution_plan_teachers.render_async(status=status, days=days)

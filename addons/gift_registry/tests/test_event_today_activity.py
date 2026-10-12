from unittest.mock import patch

from freezegun import freeze_time

from odoo import fields
from odoo.tests import TransactionCase, new_test_user, tagged

TZ = "America/Lima"


@tagged("post_install", "-at_install")
class TestEventTodayActivity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = fields.Date.context_today(cls.env["gift.registry"].with_context(tz=TZ))
        cls.cron = cls.env.ref("gift_registry.ir_cron_gift_registry_event_today")
        cls.todo_type = cls.env.ref("mail.mail_activity_data_todo")
        cls.seller = new_test_user(
            cls.env, login="lr_vendedora", name="Vera Vendedora",
            groups="base.group_user,gift_registry.group_gift_registry_user")
        cls.manager = new_test_user(
            cls.env, login="lr_administradora", name="Alba Administradora",
            groups="base.group_user,gift_registry.group_gift_registry_manager")
        cls.owner = cls.env["res.partner"].create(
            {"name": "Ana Pérez", "email": "ana@example.com"})
        cls.coffee_maker, cls.blender = cls.env["product.product"].create(
            [{"name": "Cafetera"}, {"name": "Licuadora"}])
        cls.gift_list = cls._create_list("Baby shower de Ana", cls.today, cls.seller)

    @classmethod
    def _create_list(cls, title, event_date, user, activate=True):
        """Lista con 2 cafeteras y 3 licuadoras deseadas (5 regalos)."""
        registry = cls.env["gift.registry"].create({
            "title": title,
            "partner_id": cls.owner.id,
            "event_type_id": cls.env.ref("gift_registry.event_type_baby_shower").id,
            "event_date": event_date,
            "user_id": user.id,
            "consent_data": True,
            "line_ids": [
                (0, 0, {"product_id": cls.coffee_maker.id, "qty_wanted": 2}),
                (0, 0, {"product_id": cls.blender.id, "qty_wanted": 3}),
            ],
        })
        if activate:
            registry.action_activate()
        return registry

    def _run_cron(self):
        # Ejecuta la tarea programada real, con la zona horaria que define su código
        with self.enter_registry_test_mode():
            self.cron.method_direct_trigger()

    def _notices(self, registries):
        """Avisos de esas listas, incluidos los ya marcados como hechos (archivados)."""
        return self.env["mail.activity"].with_context(active_test=False).search([
            ("res_model", "=", "gift.registry"),
            ("res_id", "in", registries.ids),
            ("activity_type_id", "=", self.todo_type.id),
        ])

    def _set_gifted(self, coffee_makers, blenders):
        """Simula regalos recibidos: el núcleo no vende, lo hacen la caja y ventas."""
        gifted = {self.coffee_maker: coffee_makers, self.blender: blenders}
        line_class = self.registry["gift.registry.line"]
        with patch.object(
                line_class, "_get_gifted_qty", lambda line: gifted[line.product_id]):
            self.gift_list.line_ids._compute_qty_gifted()

    def test_01_activity_on_event_day(self):
        tomorrow_list = self._create_list(
            "Boda de mañana", fields.Date.add(self.today, days=1), self.seller)
        draft_list = self._create_list(
            "Cumpleaños en borrador", self.today, self.seller, activate=False)
        self._run_cron()

        notice = self._notices(self.gift_list)
        self.assertEqual(len(notice), 1)
        self.assertEqual(notice.user_id, self.seller)
        self.assertEqual(notice.date_deadline, self.today)
        self.assertEqual(
            notice.summary,
            f"Hoy: Baby shower de Ana · {self.gift_list.name} · 0 de 5 regalos cubiertos (0 %)")
        # Ni las listas de otro día ni las que no están activas generan aviso
        self.assertFalse(self._notices(tomorrow_list | draft_list))

    def test_02_no_duplicate(self):
        self._run_cron()
        self._run_cron()
        notice = self._notices(self.gift_list)
        self.assertEqual(len(notice), 1)

        # Marcarlo como hecho o cancelarlo no hace que reaparezca ese mismo día
        notice.action_done()
        self._run_cron()
        self.assertEqual(len(self._notices(self.gift_list)), 1)
        self._notices(self.gift_list).unlink()
        self._run_cron()
        self.assertFalse(self._notices(self.gift_list))

    def test_03_summary_reflects_progress(self):
        prefix = f"Hoy: Baby shower de Ana · {self.gift_list.name} · "
        self._set_gifted(coffee_makers=2, blenders=1)
        self.assertEqual(
            self.gift_list._get_event_today_summary(),
            prefix + "3 de 5 regalos cubiertos (60 %)")

        # Cafeteras de más no compensan las licuadoras que faltan
        self._set_gifted(coffee_makers=5, blenders=1)
        self.assertEqual(
            self.gift_list._get_event_today_summary(),
            prefix + "3 de 5 regalos cubiertos (60 %)")

        self._set_gifted(coffee_makers=2, blenders=3)
        self._run_cron()
        self.assertEqual(self._notices(self.gift_list).summary, prefix + "Lista completa")

    def test_04_without_responsible_goes_to_managers(self):
        no_user_list = self._create_list(
            "Boda sin responsable", self.today, self.env["res.users"])
        former_seller = new_test_user(
            self.env, login="lr_exvendedor",
            groups="base.group_user,gift_registry.group_gift_registry_user")
        former_list = self._create_list("Boda de un exvendedor", self.today, former_seller)
        former_seller.active = False
        self._run_cron()

        managers = self.env.ref(
            "gift_registry.group_gift_registry_manager").all_user_ids.filtered("active")
        self.assertIn(self.manager, managers)
        self.assertNotIn(self.seller, managers)
        for registry in (no_user_list, former_list):
            notices = self._notices(registry)
            self.assertEqual(len(notices), len(managers))
            self.assertEqual(notices.user_id, managers)

    def test_05_today_is_the_date_in_peru(self):
        # 10/03 02:30 UTC son las 21:30 del 09/03 en Lima: el evento "de hoy" es el del 9
        with freeze_time("2030-03-10 02:30:00"):
            lima_today_list = self._create_list("Evento del 9", "2030-03-09", self.seller)
            utc_today_list = self._create_list("Evento del 10", "2030-03-10", self.seller)
            self._run_cron()
            self.assertEqual(
                self._notices(lima_today_list).date_deadline, fields.Date.to_date("2030-03-09"))
            self.assertFalse(self._notices(utc_today_list))

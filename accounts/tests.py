import json

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from .models import CustomUser, Label, Organization, Project


class AccountsFlowTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_signup_creates_annotator_profile(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "annotator1",
                "email": "annotator1@example.com",
                "first_name": "Jane",
                "last_name": "Worker",
                "phone_number": "+12345678901",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("login"))

        user = User.objects.get(username="annotator1")
        profile = user.custom_profile
        self.assertEqual(profile.role, CustomUser.ROLE_ANNOTATOR)
        self.assertEqual(profile.phone_number, "+12345678901")
        self.assertEqual(profile.assigned_s3_path, "")
        self.assertFalse(profile.is_verified)

    def test_login_blocks_unverified_user(self):
        user = User.objects.create_user(username="u1", password="Pass12345!")
        CustomUser.objects.create(
            django_user=user,
            role=CustomUser.ROLE_ANNOTATOR,
            is_verified=False,
        )

        response = self.client.post(
            reverse("login"),
            {"username": "u1", "password": "Pass12345!"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not verified")

    def test_api_login_includes_assigned_s3_path(self):
        user = User.objects.create_user(username="apiu", password="Pass12345!")
        owner_user = User.objects.create_user(username="assigner_api", password="Pass12345!")
        owner_profile = CustomUser.objects.create(
            django_user=owner_user,
            role=CustomUser.ROLE_ASSIGNER,
            is_verified=True,
        )
        organization = Organization.objects.create(name="api-org", owner=owner_profile)
        project = Project.objects.create(
            name="Road QA",
            description="",
            owner=owner_profile,
            organization=organization,
        )
        Label.objects.create(project=project, name="pothole")
        Label.objects.create(project=project, name="crack")

        CustomUser.objects.create(
            django_user=user,
            role=CustomUser.ROLE_ANNOTATOR,
            is_verified=True,
            assigned_s3_path="raiotransection/test/worker/frames/images",
            assigned_project=project,
        )

        response = self.client.post(
            reverse("api_login"),
            data=json.dumps({"username": "apiu", "password": "Pass12345!"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(
            payload["user"]["assigned_s3_path"],
            "raiotransection/test/worker/frames/images",
        )
        self.assertEqual(payload["user"]["assigned_project"]["name"], "Road QA")
        self.assertEqual(payload["user"]["assigned_project_labels"], ["crack", "pothole"])

    def test_assigner_can_assign_bucket_path_and_project_to_annotator(self):
        assigner_user = User.objects.create_user(username="assigner1", password="Pass12345!")
        assigner_profile = CustomUser.objects.create(
            django_user=assigner_user,
            role=CustomUser.ROLE_ASSIGNER,
            is_verified=True,
        )
        organization = Organization.objects.create(name="assigner-org", owner=assigner_profile)
        project = Project.objects.create(
            name="Lane Detection",
            description="",
            owner=assigner_profile,
            organization=organization,
        )

        annotator_user = User.objects.create_user(username="annotator2", password="Pass12345!")
        annotator_profile = CustomUser.objects.create(
            django_user=annotator_user,
            role=CustomUser.ROLE_ANNOTATOR,
            is_verified=True,
        )

        self.client.force_login(assigner_user)
        response = self.client.post(
            reverse("assigner_dash"),
            {
                "action": "assign_annotator",
                "annotator_id": annotator_profile.id,
                "assigned_s3_path": "raiotransection/test/worker/frames/videos",
                "assigned_project_id": project.id,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("assigner_dash"))

        annotator_profile.refresh_from_db()
        self.assertEqual(
            annotator_profile.assigned_s3_path,
            "raiotransection/test/worker/frames/videos",
        )
        self.assertEqual(annotator_profile.assigned_project_id, project.id)

    def test_assigner_can_create_project_and_label(self):
        assigner_user = User.objects.create_user(username="assigner2", password="Pass12345!")
        CustomUser.objects.create(
            django_user=assigner_user,
            role=CustomUser.ROLE_ASSIGNER,
            is_verified=True,
        )

        self.client.force_login(assigner_user)
        response = self.client.post(
            reverse("assigner_dash"),
            {
                "action": "create_project",
                "project_name": "Surface Damage",
                "project_description": "Road surface defects",
            },
        )
        self.assertEqual(response.status_code, 302)
        project = Project.objects.get(name="Surface Damage")

        response = self.client.post(
            reverse("assigner_dash"),
            {
                "action": "create_label",
                "project_id": project.id,
                "label_name": "patch",
                "label_color": "#123456",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Label.objects.filter(project=project, name="patch", color="#123456").exists())

    def test_non_assigner_cannot_update_assignment(self):
        reviewer_user = User.objects.create_user(username="reviewer1", password="Pass12345!")
        CustomUser.objects.create(
            django_user=reviewer_user,
            role=CustomUser.ROLE_REVIEWER,
            is_verified=True,
        )

        annotator_user = User.objects.create_user(username="annotator3", password="Pass12345!")
        annotator_profile = CustomUser.objects.create(
            django_user=annotator_user,
            role=CustomUser.ROLE_ANNOTATOR,
            is_verified=True,
        )

        self.client.force_login(reviewer_user)
        response = self.client.post(
            reverse("assigner_dash"),
            {
                "action": "assign_annotator",
                "annotator_id": annotator_profile.id,
                "assigned_s3_path": "raiotransection/test/blocked/path",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dashboard"))

        annotator_profile.refresh_from_db()
        self.assertEqual(annotator_profile.assigned_s3_path, "")

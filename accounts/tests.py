import json
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from .models import AnnotatorBucketAssignment, CustomUser, Label, Organization, Project


class AccountsFlowTests(TestCase):
    def setUp(self):
        self.client = Client()

    def _create_project(self, owner_profile, name="Road QA", organization_name="road-qa-org"):
        organization = Organization.objects.create(name=organization_name, owner=owner_profile)
        return Project.objects.create(
            name=name,
            description="",
            owner=owner_profile,
            organization=organization,
        )

    def _bucket_progress_payload(self, **overrides):
        payload = {
            "version": 1,
            "display_name": "Frames bucket",
            "s3_path": "raiotransection/test/worker/frames/images",
            "project_name": "Road QA",
            "annotator_username": "annotator",
            "input_bucket": "raiotransection",
            "input_prefix": "test/worker/frames/images",
            "progress_json_bucket": "raiotransection",
            "progress_json_key": "test/worker/frames/images/annotation_progress.json",
            "progress_json_s3_uri": "s3://raiotransection/test/worker/frames/images/annotation_progress.json",
            "total_frames": 10,
            "annotated_frames": 0,
            "pending_frames": 10,
            "progress_percent": 0.0,
            "status": "queue",
            "status_label": "Queue",
            "status_badge_class": "bg-secondary",
            "status_bar_class": "bg-secondary",
            "manual_complete": False,
            "manual_complete_by": "",
            "manual_complete_at_utc": "",
            "updated_at_utc": "2026-03-07T00:00:00Z",
            "annotation_entries": {},
            "sync_error": "",
        }
        payload.update(overrides)
        return payload

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

    def test_api_login_includes_bucket_assignments(self):
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

        profile = CustomUser.objects.create(
            django_user=user,
            role=CustomUser.ROLE_ANNOTATOR,
            is_verified=True,
            assigned_s3_path="raiotransection/test/worker/frames/images",
            assigned_project=project,
        )
        AnnotatorBucketAssignment.objects.create(
            annotator=profile,
            project=project,
            s3_path="raiotransection/test/worker/frames/images",
            display_name="Images bucket",
        )
        AnnotatorBucketAssignment.objects.create(
            annotator=profile,
            project=project,
            s3_path="raiotransection/test/worker/frames/videos",
            display_name="Videos bucket",
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
        self.assertEqual(len(payload["user"]["bucket_assignments"]), 2)
        self.assertEqual(payload["user"]["bucket_assignments"][0]["project_name"], "Road QA")

    def test_assigner_can_assign_multiple_buckets_to_annotator(self):
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
                "action": "add_bucket_assignment",
                "annotator_id": annotator_profile.id,
                "assigned_s3_path": "raiotransection/test/worker/frames/videos",
                "assigned_project_id": project.id,
                "display_name": "Video bucket",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("assigner_dash"))

        annotator_profile.refresh_from_db()
        assignments = list(AnnotatorBucketAssignment.objects.filter(annotator=annotator_profile))
        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0].s3_path, "raiotransection/test/worker/frames/videos")
        self.assertEqual(assignments[0].project_id, project.id)

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

    def test_admin_dashboard_renders_bucket_progress(self):
        admin_user = User.objects.create_user(username="admin_progress", password="Pass12345!")
        admin_profile = CustomUser.objects.create(
            django_user=admin_user,
            role=CustomUser.ROLE_ADMIN,
            is_verified=True,
        )
        project = self._create_project(
            admin_profile,
            name="Road QA",
            organization_name="admin-progress-org",
        )
        annotator_user = User.objects.create_user(username="annotator_admin_view", password="Pass12345!")
        annotator_profile = CustomUser.objects.create(
            django_user=annotator_user,
            role=CustomUser.ROLE_ANNOTATOR,
            is_verified=True,
        )
        AnnotatorBucketAssignment.objects.create(
            annotator=annotator_profile,
            project=project,
            s3_path="raiotransection/test/worker/frames/images",
            display_name="Frames bucket",
        )

        self.client.force_login(admin_user)
        with mock.patch(
            "accounts.views._sync_assignment_progress",
            return_value=self._bucket_progress_payload(
                status="in_progress",
                status_label="In Progress",
                status_badge_class="bg-warning text-dark",
                status_bar_class="bg-warning",
                progress_percent=50.0,
                annotated_frames=5,
                pending_frames=5,
            ),
        ) as sync_progress:
            response = self.client.get(reverse("admin_dash"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "In Progress")
        self.assertContains(response, "50%")
        self.assertContains(response, "annotation_progress.json")
        self.assertEqual(sync_progress.call_count, 1)

    def test_assigner_dashboard_renders_bucket_progress(self):
        assigner_user = User.objects.create_user(username="assigner_progress", password="Pass12345!")
        assigner_profile = CustomUser.objects.create(
            django_user=assigner_user,
            role=CustomUser.ROLE_ASSIGNER,
            is_verified=True,
        )
        project = self._create_project(
            assigner_profile,
            name="Surface QA",
            organization_name="assigner-progress-org",
        )
        annotator_user = User.objects.create_user(username="annotator_assigner_view", password="Pass12345!")
        annotator_profile = CustomUser.objects.create(
            django_user=annotator_user,
            role=CustomUser.ROLE_ANNOTATOR,
            is_verified=True,
        )
        AnnotatorBucketAssignment.objects.create(
            annotator=annotator_profile,
            project=project,
            s3_path="raiotransection/test/worker/frames/images",
            display_name="Frames bucket",
        )

        self.client.force_login(assigner_user)
        with mock.patch(
            "accounts.views._sync_assignment_progress",
            return_value=self._bucket_progress_payload(
                status="in_progress",
                status_label="In Progress",
                status_badge_class="bg-warning text-dark",
                status_bar_class="bg-warning",
                progress_percent=40.0,
                annotated_frames=4,
                pending_frames=6,
                project_name="Surface QA",
            ),
        ) as sync_progress:
            response = self.client.get(reverse("assigner_dash"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "In Progress")
        self.assertContains(response, "40%")
        self.assertContains(response, "Tracking JSON")
        self.assertEqual(sync_progress.call_count, 1)

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
                "action": "add_bucket_assignment",
                "annotator_id": annotator_profile.id,
                "assigned_s3_path": "raiotransection/test/blocked/path",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dashboard"))

        annotator_profile.refresh_from_db()
        self.assertEqual(AnnotatorBucketAssignment.objects.filter(annotator=annotator_profile).count(), 0)

    def test_annotator_can_mark_bucket_complete(self):
        owner_user = User.objects.create_user(username="assigner_for_complete", password="Pass12345!")
        owner_profile = CustomUser.objects.create(
            django_user=owner_user,
            role=CustomUser.ROLE_ASSIGNER,
            is_verified=True,
        )
        project = self._create_project(
            owner_profile,
            name="Completion QA",
            organization_name="annotator-complete-org",
        )
        annotator_user = User.objects.create_user(username="annotator_complete", password="Pass12345!")
        annotator_profile = CustomUser.objects.create(
            django_user=annotator_user,
            role=CustomUser.ROLE_ANNOTATOR,
            is_verified=True,
        )
        assignment = AnnotatorBucketAssignment.objects.create(
            annotator=annotator_profile,
            project=project,
            s3_path="raiotransection/test/worker/frames/images",
            display_name="Frames bucket",
        )

        self.client.force_login(annotator_user)
        with mock.patch(
            "accounts.views._sync_assignment_progress",
            return_value=self._bucket_progress_payload(
                status="complete",
                status_label="Complete",
                status_badge_class="bg-success",
                status_bar_class="bg-success",
                manual_complete=True,
                manual_complete_by="annotator_complete",
                manual_complete_at_utc="2026-03-07T10:15:00Z",
                annotated_frames=10,
                pending_frames=0,
                progress_percent=100.0,
            ),
        ) as sync_progress:
            response = self.client.post(
                reverse("anotater_dash"),
                {
                    "action": "set_bucket_completion",
                    "assignment_id": assignment.id,
                    "manual_complete": "1",
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("anotater_dash"))
        _, kwargs = sync_progress.call_args
        self.assertTrue(kwargs["manual_complete_override"])
        self.assertEqual(kwargs["manual_actor"], "annotator_complete")

    def test_reviewer_dashboard_renders_bucket_progress(self):
        reviewer_user = User.objects.create_user(username="reviewer_progress", password="Pass12345!")
        CustomUser.objects.create(
            django_user=reviewer_user,
            role=CustomUser.ROLE_REVIEWER,
            is_verified=True,
        )
        owner_user = User.objects.create_user(username="assigner_reviewer_progress", password="Pass12345!")
        owner_profile = CustomUser.objects.create(
            django_user=owner_user,
            role=CustomUser.ROLE_ASSIGNER,
            is_verified=True,
        )
        project = self._create_project(
            owner_profile,
            name="Reviewer QA",
            organization_name="reviewer-progress-org",
        )
        annotator_user = User.objects.create_user(username="annotator_reviewer_view", password="Pass12345!")
        annotator_profile = CustomUser.objects.create(
            django_user=annotator_user,
            role=CustomUser.ROLE_ANNOTATOR,
            is_verified=True,
        )
        AnnotatorBucketAssignment.objects.create(
            annotator=annotator_profile,
            project=project,
            s3_path="raiotransection/test/worker/frames/images",
            display_name="Frames bucket",
        )

        self.client.force_login(reviewer_user)
        with mock.patch(
            "accounts.views._sync_assignment_progress",
            return_value=self._bucket_progress_payload(
                status="in_progress",
                status_label="In Progress",
                status_badge_class="bg-warning text-dark",
                status_bar_class="bg-warning",
                progress_percent=60.0,
                annotated_frames=6,
                pending_frames=4,
                project_name="Reviewer QA",
                annotator_username="annotator_reviewer_view",
            ),
        ) as sync_progress:
            response = self.client.get(reverse("reviewer_dash"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Assigned Bucket Progress")
        self.assertContains(response, "In Progress")
        self.assertContains(response, "60%")
        self.assertEqual(sync_progress.call_count, 1)

    def test_dashboard_redirects_by_role(self):
        admin_user = User.objects.create_user(username="admin1", password="Pass12345!")
        CustomUser.objects.create(django_user=admin_user, role=CustomUser.ROLE_ADMIN, is_verified=True)

        assigner_user = User.objects.create_user(username="assigner3", password="Pass12345!")
        CustomUser.objects.create(django_user=assigner_user, role=CustomUser.ROLE_ASSIGNER, is_verified=True)

        reviewer_user = User.objects.create_user(username="reviewer2", password="Pass12345!")
        CustomUser.objects.create(django_user=reviewer_user, role=CustomUser.ROLE_REVIEWER, is_verified=True)

        annotator_user = User.objects.create_user(username="annotator4", password="Pass12345!")
        CustomUser.objects.create(django_user=annotator_user, role=CustomUser.ROLE_ANNOTATOR, is_verified=True)

        redirect_expectations = [
            (admin_user, reverse("admin_dash")),
            (assigner_user, reverse("assigner_dash")),
            (reviewer_user, reverse("reviewer_dash")),
            (annotator_user, reverse("anotater_dash")),
        ]

        for user, expected_url in redirect_expectations:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(reverse("dashboard"))
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, expected_url)
                self.client.logout()

    def test_admin_dashboard_supports_project_and_assignment_workflow(self):
        admin_user = User.objects.create_user(username="admin_ops", password="Pass12345!")
        admin_profile = CustomUser.objects.create(
            django_user=admin_user,
            role=CustomUser.ROLE_ADMIN,
            is_verified=True,
        )
        annotator_user = User.objects.create_user(username="annotator5", password="Pass12345!")
        annotator_profile = CustomUser.objects.create(
            django_user=annotator_user,
            role=CustomUser.ROLE_ANNOTATOR,
            is_verified=True,
        )

        self.client.force_login(admin_user)
        response = self.client.post(
            reverse("admin_dash"),
            {
                "action": "create_project",
                "project_name": "Admin Project",
                "project_description": "Created by admin dashboard",
            },
        )
        self.assertEqual(response.status_code, 302)
        project = Project.objects.get(name="Admin Project")
        self.assertEqual(project.owner, admin_profile)

        response = self.client.post(
            reverse("admin_dash"),
            {
                "action": "create_label",
                "project_id": project.id,
                "label_name": "damage",
                "label_color": "#abcdef",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Label.objects.filter(project=project, name="damage").exists())

        response = self.client.post(
            reverse("admin_dash"),
            {
                "action": "add_bucket_assignment",
                "annotator_id": annotator_profile.id,
                "assigned_s3_path": "raiotransection/admin/project/path",
                "assigned_project_id": project.id,
                "display_name": "Admin bucket",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            AnnotatorBucketAssignment.objects.filter(
                annotator=annotator_profile,
                project=project,
                s3_path="raiotransection/admin/project/path",
            ).exists()
        )

    def test_assigner_dashboard_requires_login_and_role(self):
        response = self.client.get(reverse("assigner_dash"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

        annotator_user = User.objects.create_user(username="annotator6", password="Pass12345!")
        CustomUser.objects.create(
            django_user=annotator_user,
            role=CustomUser.ROLE_ANNOTATOR,
            is_verified=True,
        )
        self.client.force_login(annotator_user)
        response = self.client.get(reverse("assigner_dash"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dashboard"))

    def test_core_urls_and_protected_redirects(self):
        root_response = self.client.get(reverse("root_login"))
        self.assertEqual(root_response.status_code, 200)
        self.assertContains(root_response, "Login")

        protected_urls = [
            reverse("dashboard"),
            reverse("admin_dash"),
            reverse("assigner_dash"),
            reverse("anotater_dash"),
            reverse("reviewer_dash"),
            reverse("profile"),
        ]
        for url in protected_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("login"), response.url)

    def test_security_settings_are_hardened_for_runtime(self):
        self.assertTrue(settings.SECURE_CONTENT_TYPE_NOSNIFF)
        self.assertEqual(settings.X_FRAME_OPTIONS, "DENY")
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, "Lax")
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertEqual(settings.SECURE_REFERRER_POLICY, "same-origin")
        self.assertEqual(settings.SECURE_CROSS_ORIGIN_OPENER_POLICY, "same-origin")
        self.assertEqual(settings.SECURE_CROSS_ORIGIN_RESOURCE_POLICY, "same-origin")

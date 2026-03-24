from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from marketplace.models import Category, Favorite, Item, ItemImage, Message, Report, User


class Command(BaseCommand):
    help = "Seed deterministic demo data (users, categories, listings, images, messages, reports, favorites)."

    def handle(self, *args, **options):
        with transaction.atomic():
            self.stdout.write(self.style.NOTICE("Seeding demo data..."))
            users = self._create_users()
            categories = self._create_categories()
            items = self._create_items(users, categories)
            self._attach_images(items)
            self._create_messages(users, items)
            self._create_favorites(users, items)
            self._create_reports(users, items)
        self.stdout.write(self.style.SUCCESS("Demo data ready."))

    def _create_users(self):
        data = [
            dict(
                username="demo_user",
                first_name="Demo",
                last_name="User",
                email="demo@uwindsor.ca",
                university_email="demo@uwindsor.ca",
                student_id="UWIN12345",
                is_staff=False,
            ),
            dict(
                username="seller_one",
                first_name="Sarah",
                last_name="Lee",
                email="sarah.lee@uwindsor.ca",
                university_email="sarah.lee@uwindsor.ca",
                student_id="UWIN54321",
                is_staff=False,
            ),
            dict(
                username="buyer_one",
                first_name="Alex",
                last_name="Chen",
                email="alex.chen@uwindsor.ca",
                university_email="alex.chen@uwindsor.ca",
                student_id="UWIN67890",
                is_staff=False,
            ),
            dict(
                username="staff_mod",
                first_name="Priya",
                last_name="Singh",
                email="priya.singh@uwindsor.ca",
                university_email="priya.singh@uwindsor.ca",
                student_id="UWIN11111",
                is_staff=True,
            ),
        ]
        users = {}
        for entry in data:
            user, created = User.objects.get_or_create(username=entry["username"], defaults=entry)
            if created:
                user.set_password("password123")
            else:
                for field, value in entry.items():
                    setattr(user, field, value)
            user.is_active = True
            user.save()
            users[entry["username"]] = user
        return users

    def _create_categories(self):
        names = [
            ("Textbooks", "textbooks"),
            ("Electronics", "electronics"),
            ("Furniture", "furniture"),
            ("Kitchen", "kitchen"),
            ("Clothing", "clothing"),
            ("Sports", "sports"),
            ("Appliances", "appliances"),
            ("Other", "other"),
        ]
        categories = {}
        for name, slug in names:
            cat, _ = Category.objects.get_or_create(name=name, defaults={"slug": slug})
            if cat.slug != slug:
                cat.slug = slug
                cat.save(update_fields=["slug"])
            categories[slug] = cat
        return categories

    def _create_items(self, users, categories):
        now = timezone.now()
        items_data = [
            dict(
                title="MacBook Air M2",
                description="Lightly used M2 Air, 8GB/256GB. Great battery life.",
                price="999.00",
                condition=Item.CONDITION_LIKE_NEW,
                status=Item.STATUS_PUBLISHED,
                category=categories["electronics"],
                seller=users["seller_one"],
                negotiable=True,
                created_at=now - timedelta(days=5),
            ),
            dict(
                title="Algorithms Textbook",
                description="CLRS 4th Edition with highlights in a few chapters.",
                price="45.00",
                condition=Item.CONDITION_GOOD,
                status=Item.STATUS_PUBLISHED,
                category=categories["textbooks"],
                seller=users["seller_one"],
                negotiable=False,
                created_at=now - timedelta(days=3),
            ),
            dict(
                title="Standing Desk",
                description="IKEA Bekant sit/stand desk, black, very sturdy.",
                price="210.00",
                condition=Item.CONDITION_GOOD,
                status=Item.STATUS_PUBLISHED,
                category=categories["furniture"],
                seller=users["seller_one"],
                negotiable=True,
                created_at=now - timedelta(days=2),
            ),
            dict(
                title="PS5 Bundle",
                description="PS5 with two controllers and Spider-Man 2. Works perfectly.",
                price="580.00",
                condition=Item.CONDITION_LIKE_NEW,
                status=Item.STATUS_DRAFT,
                category=categories["electronics"],
                seller=users["seller_one"],
                negotiable=False,
                created_at=now - timedelta(days=1),
            ),
            dict(
                title="Winter Jacket",
                description="Canada Goose-style parka, size M, very warm.",
                price="150.00",
                condition=Item.CONDITION_GOOD,
                status=Item.STATUS_SOLD,
                category=categories["clothing"],
                seller=users["seller_one"],
                negotiable=False,
                created_at=now - timedelta(days=7),
            ),
            dict(
                title="Blender",
                description="Ninja blender with two cups, perfect for smoothies.",
                price="60.00",
                condition=Item.CONDITION_FAIR,
                status=Item.STATUS_PUBLISHED,
                category=categories["kitchen"],
                seller=users["buyer_one"],
                negotiable=True,
                created_at=now - timedelta(days=4),
            ),
        ]
        items = []
        for data in items_data:
            item, created = Item.objects.get_or_create(
                title=data["title"],
                seller=data["seller"],
                defaults=data,
            )
            if not created:
                for field, value in data.items():
                    setattr(item, field, value)
                item.save()
            items.append(item)
        return items

    def _attach_images(self, items):
        tiny_gif = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00"
            b"\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21"
            b"\xf9\x04\x00\x00\x00\x00\x00\x2c\x00\x00"
            b"\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44"
            b"\x01\x00\x3b"
        )
        media_items_dir = Path(settings.MEDIA_ROOT) / "items"
        preferred_images = [
            path for path in media_items_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        ] if media_items_dir.exists() else []

        for index, item in enumerate(items):
            existing_images = list(item.images.all())
            has_real_image = any(Path(image.image.name).suffix.lower() != ".gif" for image in existing_images)
            if has_real_image:
                continue

            if existing_images:
                for image in existing_images:
                    image.image.delete(save=False)
                    image.delete()

            img = ItemImage(item=item)
            if preferred_images:
                source = preferred_images[index % len(preferred_images)]
                img.image.save(
                    f"items/demo_{item.pk}{source.suffix.lower()}",
                    ContentFile(source.read_bytes()),
                    save=True,
                )
            else:
                img.image.save(f"items/{item.pk}_1.gif", ContentFile(tiny_gif), save=True)

    def _create_messages(self, users, items):
        buyer = users["buyer_one"]
        seller = users["seller_one"]
        item = items[0]
        thread = [
            ("Hi, is this still available?", buyer),
            ("Yes, it is. Happy to meet on campus.", seller),
            ("Great, can you do $950?", buyer),
            ("950 works. Let's meet at library at 3pm.", seller),
        ]
        for idx, (body, sender) in enumerate(thread):
            recipient = seller if sender == buyer else buyer
            Message.objects.get_or_create(
                item=item,
                sender=sender,
                recipient=recipient,
                body=body,
                defaults={
                    "created_at": timezone.now() - timedelta(minutes=10 * (len(thread) - idx)),
                },
            )

    def _create_favorites(self, users, items):
        Favorite.objects.get_or_create(user=users["demo_user"], item=items[0])
        Favorite.objects.get_or_create(user=users["demo_user"], item=items[1])
        Favorite.objects.get_or_create(user=users["buyer_one"], item=items[2])

    def _create_reports(self, users, items):
        staff = users["staff_mod"]
        buyer = users["buyer_one"]
        Report.objects.get_or_create(
            item=items[5],
            reporter=buyer,
            defaults={
                "reason": Report.REASON_OTHER,
                "comment": "Please verify condition; listing seems vague.",
                "status": Report.STATUS_OPEN,
            },
        )
        Report.objects.get_or_create(
            item=items[0],
            reporter=staff,
            defaults={
                "reason": Report.REASON_SPAM,
                "comment": "Checking duplicate posts.",
                "status": Report.STATUS_RESOLVED,
                "reviewed_by": staff,
                "reviewed_at": timezone.now() - timedelta(days=1),
            },
        )

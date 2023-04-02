import json

from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Avg
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404

from django.utils.decorators import method_decorator
from django.views import View

from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, ListView, CreateView, UpdateView, DeleteView

from django_project import settings
from vacancies.models import Vacancy, Skill
from vacancies.serializers import VacancySerializer


def hello(request):
    return HttpResponse("Hello World")


class VacancyListView(ListView):
    model = Vacancy

    def get(self, request, *args, **kwargs):
        super().get(request, *args, **kwargs)

        search_text = request.GET.get("text", None)
        if search_text:
            self.object_list = self.object_list.filter(text=search_text)

        self.object_list = self.object_list.select_related("user").prefetch_related("skills").order_by("text")

        paginator = Paginator(self.object_list, settings.TOTAL_ON_PAGE)
        page_number = int(request.GET.get("page", 1))

        page_obj = paginator.get_page(page_number)

        # """
        # 1 - 1:10
        # 2 - 11:20
        # 3 - 21:30
        # """
        # total = self.object_list.count()
        # page_number = int(request.GET.get("page", 1))
        # offset = (page_number - 1) * settings.TOTAL_ON_PAGE
        #
        # if offset < total:
        # 	self.object_list = self.object_list[offset:offset + settings.TOTAL_ON_PAGE]
        # else:
        # 	self.object_list = self.object_list[offset:total]

        # vacancies = []
        # for vacancy in page_obj:
        #     vacancies.append({
        #         "id": vacancy.id,
        #         "text": vacancy.text,
        #         "slug": vacancy.slug,
        #         "status": vacancy.status,
        #         "created": vacancy.created,
        #         "username": vacancy.user.username,
        #         # "skills": list(vacancy.skills.all().values_list("name", flat=True))
        #         "skills": list(map(str, vacancy.skills.all()))
        #     })

        list(map(lambda x: setattr(x, "username", x.user.username if x.user else None), page_obj))

        response = {
            # "items": vacancies,
            "items": VacancySerializer(page_obj, many=True).data,
            "num_pages": paginator.num_pages,
            "total": paginator.count
        }

        # return JsonResponse(response, safe=False)
        return JsonResponse(response, safe=False, json_dumps_params={"ensure_ascii": False, "indent": 4})


class VacancyDetailView(DetailView):
    model = Vacancy

    def get(self, request, *args, **kwargs):
        vacancy = self.get_object()

        return JsonResponse({
            "id": vacancy.id,
            "text": vacancy.text,
            "slug": vacancy.slug,
            "status": vacancy.status,
            "created": vacancy.created,
            "user": vacancy.user_id,
            "skills": list(vacancy.skills.all().values_list("name", flat=True))
        })


@method_decorator(csrf_exempt, name="dispatch")
class VacancyCreateView(CreateView):
    model = Vacancy
    fields = ["slug", "text", "status", "created", "user", "skills"]

    def post(self, request, *args, **kwargs):
        vacancy_data = json.loads(request.body)

        vacancy = Vacancy.objects.create(
            slug=vacancy_data["slug"],
            text=vacancy_data["text"],
            status=vacancy_data["status"]
            # user_id=vacancy_data["user_id"],
        )

        vacancy.user = get_object_or_404(User, pk=vacancy_data["user_id"])

        for skill in vacancy_data["skills"]:
            skill_obj, created = Skill.objects.get_or_create(
                name=skill,
                defaults={
                    "is_active": True,
                })
            # try:
            #     skill_obj = Skill.objects.get(name=skill)
            # except Skill.DoesNotExist:
            #     skill_obj = Skill.objects.create(name=skill)
            #     # return JsonResponse({"error": "Skill not found"}, status=404)
            vacancy.skills.add(skill_obj)
        vacancy.save()  # Так как метод create сам всё сохранит, но скилы надо сохранить отдельно

        return JsonResponse({
            "id": vacancy.id,
            "text": vacancy.text,
            "slug": vacancy.slug,
            "status": vacancy.status,
            "created": vacancy.created,
            "user": vacancy.user_id,
        })


@method_decorator(csrf_exempt, name="dispatch")
class VacancyUpdateView(UpdateView):
    model = Vacancy
    fields = ["slug", "text", "status", "skills"]

    def patch(self, request, *args, **kwargs):
        super().post(request, *args, **kwargs)

        vacancy_data = json.loads(request.body)

        self.object.slug = vacancy_data["slug"]
        self.object.text = vacancy_data["text"]
        self.object.status = vacancy_data["status"]

        for skill in vacancy_data["skills"]:
            try:
                skill_obj = Skill.objects.get(name=skill)
            except Skill.DoesNotExist:
                return JsonResponse({"error": "Skill not found"}, status=404)
            self.object.skills.add(skill_obj)

        self.object.save()

        return JsonResponse({
            "id": self.object.id,
            "text": self.object.text,
            "slug": self.object.slug,
            "status": self.object.status,
            "created": self.object.created,
            "user": self.object.user_id,
            "skills": list(self.object.skills.all().values_list("name", flat=True))
        })


@method_decorator(csrf_exempt, name="dispatch")
class VacancyDeleteView(DeleteView):
    model = Vacancy

    success_url = "/"

    def delete(self, request, *args, **kwargs):
        super().delete(request, *args, **kwargs)

        return JsonResponse({"status": "ok"}, status=200)


class UserVacancyDetailView(View):
    def get(self, request):
        user_qs = User.objects.annotate(vacancies=Count('vacancy'))

        paginator = Paginator(user_qs, settings.TOTAL_ON_PAGE)
        page_number = int(request.GET.get("page", 1))
        page_obj = paginator.get_page(page_number)

        users = []
        for user in page_obj:
            users.append(
                {
                    "id": user.id,
                    "name": user.username,
                    "vacancies": user.vacancies
                }
            )

            response = {
                "items": users,
                "num_pages": paginator.num_pages,
                "total": paginator.count,
                "avg": user_qs.aggregate(avg=Avg('vacancies'))["avg"]
            }

        return JsonResponse(response, safe=False)

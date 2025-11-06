from django.contrib import admin
from .models import Company, PersonInNeed, CV, CSRRep, PA, Request, FlaggedRequest

admin.site.register(Company)
admin.site.register(PersonInNeed)
admin.site.register(CV)
admin.site.register(CSRRep)
admin.site.register(PA)
admin.site.register(Request)
admin.site.register(FlaggedRequest)

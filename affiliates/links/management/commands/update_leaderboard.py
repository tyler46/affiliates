import sys

from django.contrib.auth.models import User
from django.db.models import Sum

from affiliates.base.management.commands import QuietCommand
from affiliates.links.models import LeaderboardStanding


class Command(QuietCommand):
    help = ('Populate the leaderboard with the latest rankings.')

    def handle_quiet(self, *args, **kwargs):
        # Collect the sum of aggregated clicks stored in related Links
        # for each user.
        self.output('Collecting click counts...')
        aggregate_click_totals = User.objects.annotate(
            aggregate_link_clicks=Sum('link__aggregate_link_clicks')
        ).values_list('pk', 'aggregate_link_clicks')

        # Collect the sum of clicks stored in related DataPoints for
        # each user, stored as a dict.
        datapoint_click_totals = dict(User.objects.annotate(
            datapoint_link_clicks=Sum('link__datapoint__link_clicks')
        ).values_list('pk', 'datapoint_link_clicks'))

        # Generate a list of user pks and the total clicks we have for
        # them, and sort by click count.
        self.output('Sorting click counts...')
        total_clicks = [
            (pk, (aggregate_clicks or 0) + (datapoint_click_totals.get(pk, 0) or 0))
            for pk, aggregate_clicks in aggregate_click_totals
        ]
        total_clicks = sorted(total_clicks, lambda a, b: b[1] - a[1])

        # Regenerate the leaderboard using the sorted list of clicks.
        self.output('Updating database...')
        print 'pre-delete'
        LeaderboardStanding.objects.all().delete()
        print 'post-delete'
        new_standings = [
            LeaderboardStanding(ranking=index + 1, user_id=entry[0], metric='link_clicks',
                                value=entry[1])
            for index, entry in enumerate(total_clicks)
        ]
        for standing in new_standings:
            sys.stderr.write('{0}: {1} {2}\n'.format(standing.ranking, standing.user_id, standing.value))
        LeaderboardStanding.objects.bulk_create(new_standings, batch_size=1000)

        self.output('Done!')

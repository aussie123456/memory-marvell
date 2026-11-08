#!/usr/bin/perl
# Local preview builder for machines without Python (mirrors build.py).
# Usage: perl tools/build-local.pl [template.html] [curated.json] [dist/index.html]
# Fetches every data block with curl (Yahoo cookie+crumb for quoteSummary), injects curated.json, stamps d-meta.
use strict; use warnings; use JSON::PP; use File::Basename; use File::Path qw(make_path); use POSIX qw(strftime);
my ($tpl, $cur, $out) = ($ARGV[0] // 'template.html', $ARGV[1] // 'curated.json', $ARGV[2] // 'dist/index.html');
my $UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36';
local $/; open my $fh, '<:encoding(UTF-8)', $tpl or die $!; my $text = <$fh>; close $fh;
open $fh, '<:encoding(UTF-8)', $cur or die $!; my $curated = <$fh>; close $fh; JSON::PP->new->decode($curated);
my $J = JSON::PP->new->canonical(0);
sub esc_payload { my $s = shift; $s =~ s{</}{<\\/}g; return $s; }
sub set_block { my ($bid, $payload) = @_; $text =~ s{^(<script type="application/json" id="\Q$bid\E"[^>]*>)(.*?)(</script>)}{$1 . esc_payload($payload) . $3}mse; }
set_block('d-curated', $curated);
my $jar = "/tmp/mm-yahoo-cookies.txt"; unlink $jar;
sub curl { my ($url, @extra) = @_; my $body = `curl -sS --max-time 40 -A "$UA" @extra "$url"`; return $body; }
my $crumb = '';
if ($text =~ /data-auth="yahoo"/) {
  for my $try (1..4) { curl('https://fc.yahoo.com', '-c', $jar, '-o', ($^O eq 'MSWin32' ? 'NUL' : '/dev/null')); $crumb = curl('https://query2.finance.yahoo.com/v1/test/getcrumb', '-b', $jar, '-c', $jar); $crumb =~ s/\s+//g; last if length($crumb) && length($crumb) < 30 && $crumb !~ /[{ ]/; $crumb = ''; sleep 3 + 4*$try; }
  print "yahoo crumb: ", ($crumb ? 'ok' : 'FAILED'), "\n";
}
my %status; my $now = strftime('%Y-%m-%dT%H:%M:%SZ', gmtime);
sub uri_esc { my $s = shift; $s =~ s/([^A-Za-z0-9\-_.~])/sprintf('%%%02X', ord($1))/ge; return $s; }
$text =~ s{^(<script type="application/json" id="(d-[\w-]+)"([^>]*)>)(.*?)(</script>)}{
  my ($open, $bid, $attrs, $old, $close) = ($1, $2, $3, $4, $5);
  my $r = $open.$old.$close;
  if ($attrs =~ /data-url="([^"]+)"/) {
    my $url = $1; $url =~ s/&amp;/&/g;
    my $kind = $attrs =~ /data-kind="(\w+)"/ ? $1 : 'json'; my $auth = $attrs =~ /data-auth="(\w+)"/ ? $1 : '';
    my ($payload, $err);
    for my $attempt (0..2) {
      my $body;
      if ($auth eq 'yahoo') { if (!$crumb) { $err = 'no yahoo crumb'; last; } (my $u = $url) =~ s/\{crumb\}/uri_esc($crumb)/e; $body = curl($u, '-b', $jar); }
      else { $body = curl($url); }
      if ($kind eq 'json') { my $obj = eval { JSON::PP->new->utf8(1)->decode($body) }; if ($obj && !$@) { $payload = $J->encode($obj); last; } $err = 'bad json: '.substr($body // '', 0, 80); }
      else { if (defined $body && length($body) >= 50) { utf8::decode($body); $body =~ s{<description>.*?</description>}{}gs if $url =~ /news\.google\.com/; $payload = $J->encode($body); last; } $err = 'short body'; }
      sleep 2 + 3*$attempt;
    }
    (my $attrs2 = $attrs) =~ s/\s*data-fetched="[^"]*"//;
    if (defined $payload) { $status{$bid} = 'ok'; printf "  %-18s ok   %s chars\n", $bid, length($payload); $r = qq{<script type="application/json" id="$bid"$attrs2 data-fetched="$now">}.esc_payload($payload).$close; }
    else { $status{$bid} = 'error: '.($err // 'unknown'); printf "  %-18s FAIL %s\n", $bid, $err // '?'; }
  }
  $r;
}gmse;
set_block('d-meta', $J->encode({generated_at => $now, status => \%status, builder => 'local-perl'}));
make_path(dirname($out)); open my $oh, '>:encoding(UTF-8)', $out or die $!; print $oh $text; close $oh;
my $ok = grep { $_ eq 'ok' } values %status; printf "wrote %s; %d/%d blocks refreshed\n", $out, $ok, scalar keys %status;

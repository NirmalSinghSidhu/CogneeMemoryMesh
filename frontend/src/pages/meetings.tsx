import { useState } from "react";
import { Link } from "wouter";
import { useListMeetings, useCreateMeeting, getListMeetingsQueryKey } from "@workspace/api-client-react";
import { CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/badges";
import { Calendar, Upload, FileText } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useQueryClient } from "@tanstack/react-query";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { PageShell, HeroBanner, SurfaceCard, EmptyState } from "@/components/page-shell";

export default function Meetings() {
  const { data: meetings, isLoading } = useListMeetings();
  const createMeeting = useCreateMeeting();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");

  const handleUpload = () => {
    if (!title || !content) {
      toast({ title: "Error", description: "Title and transcript content are required", variant: "destructive" });
      return;
    }

    createMeeting.mutate(
      {
        data: {
          title,
          content,
          date: new Date().toISOString(),
          content_type: "transcript",
        },
      },
      {
        onSuccess: () => {
          toast({ title: "Success", description: "Meeting uploaded and processing started" });
          queryClient.invalidateQueries({ queryKey: getListMeetingsQueryKey() });
          setIsUploadOpen(false);
          setTitle("");
          setContent("");
        },
        onError: () => {
          toast({ title: "Error", description: "Failed to upload meeting", variant: "destructive" });
        },
      }
    );
  };

  return (
    <PageShell className="space-y-6">
      <HeroBanner
        eyebrow="Transcripts"
        eyebrowIcon={FileText}
        title="Meetings"
        description="Transcripts processed and indexed into organizational memory."
        actions={
          <Dialog open={isUploadOpen} onOpenChange={setIsUploadOpen}>
            <DialogTrigger asChild>
              <Button className="gap-2 shadow-sm">
                <Upload className="w-4 h-4" />
                Upload Transcript
              </Button>
            </DialogTrigger>
            <DialogContent className="surface-card sm:max-w-lg">
              <DialogHeader>
                <DialogTitle>Upload Meeting Transcript</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 pt-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Meeting Title</label>
                  <Input placeholder="Engineering Sync Q3" value={title} onChange={(e) => setTitle(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Transcript Content</label>
                  <Textarea
                    placeholder="Paste meeting transcript or notes here..."
                    className="min-h-[200px] font-mono text-sm"
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                  />
                </div>
                <Button className="w-full" onClick={handleUpload} disabled={createMeeting.isPending}>
                  {createMeeting.isPending ? "Processing..." : "Process Meeting"}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        }
      />

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      ) : meetings && meetings.length > 0 ? (
        <div className="grid gap-3">
          {meetings.map((meeting) => (
            <Link key={meeting.id} href={`/meetings/${meeting.id}`}>
              <SurfaceCard hover>
                <CardContent className="p-5 md:p-6">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <h3 className="text-lg font-semibold tracking-tight truncate">{meeting.title}</h3>
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-sm text-muted-foreground font-mono">
                        <span className="flex items-center gap-1.5">
                          <Calendar className="w-3.5 h-3.5" />
                          {new Date(meeting.date).toLocaleDateString()}
                        </span>
                        <span>{meeting.participant_count} participants</span>
                        <span>{meeting.entity_count} entities</span>
                        {meeting.duration_minutes != null && <span>{meeting.duration_minutes} min</span>}
                      </div>
                      {meeting.project_names && meeting.project_names.length > 0 && (
                        <div className="flex flex-wrap gap-2 mt-3">
                          {meeting.project_names.map((project) => (
                            <span
                              key={project}
                              className="px-2 py-0.5 bg-blue-500/10 text-blue-400 rounded-md text-xs font-medium border border-blue-500/20"
                            >
                              {project}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    <StatusBadge status={meeting.status} type="meeting" />
                  </div>
                </CardContent>
              </SurfaceCard>
            </Link>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={FileText}
          title="No meetings yet"
          description="Upload a transcript to start building your organizational memory."
        />
      )}
    </PageShell>
  );
}

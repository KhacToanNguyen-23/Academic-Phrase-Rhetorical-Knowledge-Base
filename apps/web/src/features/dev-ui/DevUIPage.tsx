import { useState } from "react"
import { toast } from "sonner"
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "@/components/ui/breadcrumb"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Combobox } from "@/components/ui/combobox"
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import { Field, FieldDescription, FieldGroup, FieldLabel, FieldLegend, FieldSet } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from "@/components/ui/input-group"
import { Kbd, KbdGroup } from "@/components/ui/kbd"
import { Label } from "@/components/ui/label"
import { Pagination, PaginationContent, PaginationEllipsis, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from "@/components/ui/pagination"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { Sidebar, SidebarContent, SidebarGroup, SidebarGroupContent, SidebarGroupLabel, SidebarMenu, SidebarMenuButton, SidebarMenuItem, SidebarProvider, SidebarInset } from "@/components/ui/sidebar"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { Toaster } from "@/components/ui/sonner"
import { DataState, DictionaryEntry, EvidenceLabel, LicenceStatus, PageHeader, PhraseFrame, ProvenanceTag, SeverityBadge, StatusBadge } from "@/components/domain"
import { useTheme } from "@/shared/lib/theme"

const moveOptions = [
  { label: "Frame a gap", value: "gap" },
  { label: "Describe a method", value: "method" },
  { label: "State a finding", value: "finding" },
]

function StateLabel({ name, children }: { name: string; children: React.ReactNode }) {
  return (
    <div data-demo-state={name} className="flex min-h-20 flex-col items-start justify-center gap-2 rounded-[var(--radius)] border border-border bg-card p-3">
      <span className="text-xs text-muted-foreground">{name}</span>
      {children}
    </div>
  )
}

function DevUIPage() {
  const { theme, toggle } = useTheme()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [alertOpen, setAlertOpen] = useState(false)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [choice, setChoice] = useState("gap")

  return (
    <TooltipProvider>
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-10 p-6 lg:p-10">
        <PageHeader
          title="Component inventory"
          description="A working catalogue of the Radix primitives and AP-RKB domain components. Every control uses the light/dark token set."
          actions={<Button variant="secondary" onClick={toggle}>Use {theme === "dark" ? "light" : "dark"} theme</Button>}
        />

        <section aria-labelledby="buttons-heading" className="flex flex-col gap-4">
          <div>
            <h2 id="buttons-heading" className="text-base font-semibold">Buttons and eight states</h2>
            <p className="text-sm text-muted-foreground">The primary action is teal; supporting actions stay neutral. These eight fixtures are the shared interaction contract for the controls below.</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StateLabel name="default"><Button>Review frame</Button></StateLabel>
            <StateLabel name="hover"><Button variant="secondary">Hover me</Button></StateLabel>
            <StateLabel name="focus"><Button variant="outline" autoFocus>Keyboard focus</Button></StateLabel>
            <StateLabel name="active"><Button variant="secondary" data-demo-state="active">Press state</Button></StateLabel>
            <StateLabel name="disabled"><Button disabled>Unavailable</Button></StateLabel>
            <StateLabel name="loading"><Button disabled><Spinner data-icon="inline-start" />Saving frame</Button></StateLabel>
            <StateLabel name="error"><Button variant="destructive">Resolve error</Button></StateLabel>
            <StateLabel name="success"><StatusBadge status="approved" /></StateLabel>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="xl">Landing action</Button>
            <Button variant="secondary">Secondary action</Button>
            <Button variant="ghost">Quiet action</Button>
            <Button variant="link">Text action</Button>
          </div>
        </section>

        <Separator />

        <section aria-labelledby="forms-heading" className="flex flex-col gap-4">
          <div>
            <h2 id="forms-heading" className="text-base font-semibold">Forms and selection</h2>
            <p className="text-sm text-muted-foreground">Labels remain visible, focus uses the ink ring, and errors explain the next step.</p>
          </div>
          <FieldGroup className="grid gap-4 lg:grid-cols-2">
            <Field>
              <FieldLabel htmlFor="frame-name">Frame name</FieldLabel>
              <Input id="frame-name" placeholder="e.g. Methods comparison" />
              <FieldDescription>A short name for the reviewed frame.</FieldDescription>
            </Field>
            <Field data-invalid>
              <FieldLabel htmlFor="frame-error">Source identifier</FieldLabel>
              <Input id="frame-error" aria-invalid placeholder="Enter a source identifier" />
              <FieldDescription>Source identifier needs a journal key. Example: JNL-204.</FieldDescription>
            </Field>
            <Field>
              <FieldLabel htmlFor="frame-note">Curator note</FieldLabel>
              <Textarea id="frame-note" placeholder="Record the evidence decision" />
            </Field>
            <Field>
              <FieldLabel htmlFor="inline-search">Search candidates</FieldLabel>
              <InputGroup>
                <InputGroupInput id="inline-search" placeholder="Search by frame or family" />
                <InputGroupAddon align="inline-end"><InputGroupButton variant="ghost">Search</InputGroupButton></InputGroupAddon>
              </InputGroup>
            </Field>
          </FieldGroup>
          <div className="grid gap-4 lg:grid-cols-3">
            <Field>
              <FieldLabel htmlFor="move-select">Rhetorical move</FieldLabel>
              <Select defaultValue="finding">
                <SelectTrigger id="move-select"><SelectValue placeholder="Choose a move" /></SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectLabel>Move</SelectLabel>
                    <SelectItem value="gap">Frame a gap</SelectItem>
                    <SelectItem value="method">Describe a method</SelectItem>
                    <SelectItem value="finding">State a finding</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
            <Field>
               <FieldLabel id="move-combobox-label" htmlFor="move-combobox">Searchable move</FieldLabel>
               <Combobox id="move-combobox" aria-labelledby="move-combobox-label" options={moveOptions} value={choice} onValueChange={setChoice} />
            </Field>
            <FieldSet>
              <FieldLegend variant="label">Review mode</FieldLegend>
              <RadioGroup defaultValue="careful" className="flex flex-row gap-4">
                <Field orientation="horizontal"><RadioGroupItem value="careful" id="careful" /><FieldLabel htmlFor="careful">Careful</FieldLabel></Field>
                <Field orientation="horizontal"><RadioGroupItem value="quick" id="quick" /><FieldLabel htmlFor="quick">Quick</FieldLabel></Field>
              </RadioGroup>
            </FieldSet>
          </div>
          <div className="flex flex-wrap items-center gap-6">
            <Label className="flex items-center gap-2"><Checkbox defaultChecked /> Include provenance</Label>
            <Label className="flex items-center gap-2"><Switch defaultChecked /> Show confidence</Label>
            <ToggleGroup type="single" defaultValue="all" aria-label="Evidence filter">
              <ToggleGroupItem value="all">All</ToggleGroupItem>
              <ToggleGroupItem value="review">Needs review</ToggleGroupItem>
            </ToggleGroup>
          </div>
          <Tabs defaultValue="frame">
            <TabsList variant="line">
              <TabsTrigger value="frame">Frame</TabsTrigger>
              <TabsTrigger value="evidence">Evidence</TabsTrigger>
            </TabsList>
            <TabsContent value="frame">The frame view keeps the phrase in Newsreader.</TabsContent>
            <TabsContent value="evidence">The evidence view keeps provenance beside the content.</TabsContent>
          </Tabs>
        </section>

        <Separator />

        <section aria-labelledby="overlay-heading" className="flex flex-col gap-4">
          <div>
            <h2 id="overlay-heading" className="text-base font-semibold">Menus and overlays</h2>
            <p className="text-sm text-muted-foreground">Open each control with keyboard or pointer; Escape closes the active layer.</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <DropdownMenu>
              <DropdownMenuTrigger asChild><Button variant="secondary">Actions</Button></DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuGroup>
                  <DropdownMenuLabel>Frame actions</DropdownMenuLabel>
                  <DropdownMenuItem>Open evidence</DropdownMenuItem>
                  <DropdownMenuItem>Copy frame</DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem variant="destructive">Archive frame</DropdownMenuItem>
                </DropdownMenuGroup>
              </DropdownMenuContent>
            </DropdownMenu>
            <Popover>
              <PopoverTrigger asChild><Button variant="outline">Quick note</Button></PopoverTrigger>
              <PopoverContent><div className="flex flex-col gap-2"><Label htmlFor="quick-note">Note</Label><Input id="quick-note" placeholder="Add a note" /></div></PopoverContent>
            </Popover>
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
              <DialogTrigger asChild><Button variant="secondary">Open dialog</Button></DialogTrigger>
              <DialogContent>
                <DialogHeader><DialogTitle>Review evidence</DialogTitle><DialogDescription>Confirm the frame before it enters the review queue.</DialogDescription></DialogHeader>
                <Button onClick={() => setDialogOpen(false)}>Save decision</Button>
              </DialogContent>
            </Dialog>
            <AlertDialog open={alertOpen} onOpenChange={setAlertOpen}>
              <AlertDialogTrigger asChild><Button variant="destructive">Archive</Button></AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader><AlertDialogTitle>Archive this frame?</AlertDialogTitle><AlertDialogDescription>This removes it from the active review queue. You can restore it later.</AlertDialogDescription></AlertDialogHeader>
                <AlertDialogFooter><AlertDialogCancel>Keep frame</AlertDialogCancel><AlertDialogAction>Archive frame</AlertDialogAction></AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
            <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
              <SheetTrigger asChild><Button variant="secondary">Open details</Button></SheetTrigger>
              <SheetContent><SheetHeader><SheetTitle>Evidence details</SheetTitle><SheetDescription>Source information for the selected frame.</SheetDescription></SheetHeader><div className="flex flex-col gap-3 p-4"><LicenceStatus status="unknown" /><Button variant="secondary" onClick={() => setSheetOpen(false)}>Close details</Button></div></SheetContent>
            </Sheet>
            <Tooltip><TooltipTrigger asChild><Button variant="ghost" aria-label="More information">Info</Button></TooltipTrigger><TooltipContent>Evidence comes from a self-authored sample.</TooltipContent></Tooltip>
          </div>
          <div className="max-w-md rounded-[var(--radius)] border border-border bg-card p-2">
            <Command>
              <CommandInput placeholder="Search commands" />
              <CommandList><CommandEmpty>No command found.</CommandEmpty><CommandGroup heading="Review"><CommandItem>Open evidence</CommandItem><CommandItem>Mark as reviewed</CommandItem></CommandGroup></CommandList>
            </Command>
          </div>
        </section>

        <Separator />

        <section aria-labelledby="data-heading" className="flex flex-col gap-4">
          <div>
            <h2 id="data-heading" className="text-base font-semibold">Data, feedback and domain components</h2>
            <p className="text-sm text-muted-foreground">Neutral chrome keeps the phrase and its evidence legible.</p>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader><CardTitle>Review queue</CardTitle><CardDescription>Rows keep their identity and figures aligned.</CardDescription></CardHeader>
              <CardContent><Table><TableHeader><TableRow><TableHead>Frame</TableHead><TableHead numeric>Rank</TableHead><TableHead>Status</TableHead></TableRow></TableHeader><TableBody><TableRow><TableCell>Frame a gap</TableCell><TableCell numeric>12</TableCell><TableCell><StatusBadge status="in_review" /></TableCell></TableRow><TableRow><TableCell>State a finding</TableCell><TableCell numeric>—</TableCell><TableCell><StatusBadge status="approved" /></TableCell></TableRow><TableRow><TableCell>Describe a method</TableCell><TableCell numeric>0</TableCell><TableCell><StatusBadge status="draft" /></TableCell></TableRow></TableBody></Table></CardContent>
              <CardFooter><Button variant="secondary" onClick={() => toast.success("Queue refreshed")}>Refresh queue</Button></CardFooter>
            </Card>
            <div className="flex flex-col gap-4">
              <Alert><AlertTitle>Evidence note</AlertTitle><AlertDescription>Observed examples are not journal requirements.</AlertDescription></Alert>
              <DataState state="ready" label="Reviewed frames" value={0} />
              <DataState state="ready" label="Reviewed frames" value={null} />
              <DataState state="loading" loadingLabel="Loading evidence" />
              <DataState state="empty" emptyTitle="No reviewed frames yet" emptyDescription="Review a candidate to build the evidence set for this view." emptyAction={<Button variant="secondary">Review a candidate</Button>} />
              <DataState state="error" errorTitle="Evidence could not be loaded" errorDescription="Check the connection and try the request again." onRetry={() => toast("Evidence request retried")} />
            </div>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card><CardHeader><CardTitle>Phrase frame</CardTitle><CardDescription>Self-authored sample only.</CardDescription></CardHeader><CardContent className="flex flex-col gap-4"><PhraseFrame frame="The analysis {finding} across the selected sample." /><div className="flex flex-wrap gap-2"><ProvenanceTag value="authored" /><LicenceStatus status="unknown" /><EvidenceLabel kind="observed" /><SeverityBadge value="warn" /></div></CardContent></Card>
            <DictionaryEntry headword="converge" partOfSpeech="verb" family="method comparison" rank={12} example="The two approaches converge on a shared interpretation." provenance="authored" licence="cleared" />
          </div>
          <div className="grid gap-4 md:grid-cols-3"><StateLabel name="badge success"><Badge variant="success">Approved</Badge></StateLabel><StateLabel name="badge warning"><Badge variant="warning">Needs review</Badge></StateLabel><StateLabel name="badge blocked"><Badge variant="destructive">Blocked</Badge></StateLabel></div>
          <Empty><EmptyHeader><EmptyTitle>No saved views</EmptyTitle><EmptyDescription>Create a view when a review filter is useful again.</EmptyDescription></EmptyHeader><EmptyContent><Button variant="secondary">Create a view</Button></EmptyContent></Empty>
        </section>

        <Separator />

        <section aria-labelledby="navigation-heading" className="flex flex-col gap-4">
          <div><h2 id="navigation-heading" className="text-base font-semibold">Navigation, paging and keystrokes</h2><p className="text-sm text-muted-foreground">The same active treatment is shared by sidebar and tabs.</p></div>
          <SidebarProvider defaultOpen>
            <Sidebar collapsible="none"><SidebarContent><SidebarGroup><SidebarGroupLabel>Review</SidebarGroupLabel><SidebarGroupContent><SidebarMenu><SidebarMenuItem><SidebarMenuButton isActive>Evidence queue</SidebarMenuButton></SidebarMenuItem><SidebarMenuItem><SidebarMenuButton>Dictionary</SidebarMenuButton></SidebarMenuItem></SidebarMenu></SidebarGroupContent></SidebarGroup></SidebarContent></Sidebar>
            <SidebarInset className="min-h-40"><div className="flex flex-col gap-4 p-4"><Breadcrumb><BreadcrumbList><BreadcrumbItem><BreadcrumbLink href="#">Library</BreadcrumbLink></BreadcrumbItem><BreadcrumbSeparator /><BreadcrumbItem><BreadcrumbPage>Evidence queue</BreadcrumbPage></BreadcrumbItem></BreadcrumbList></Breadcrumb><ScrollArea className="h-16 rounded-[var(--radius)] border border-border"><div className="p-3 text-sm">Scrollable evidence notes stay inside the panel.</div></ScrollArea><KbdGroup><Kbd>⌘</Kbd><Kbd>K</Kbd></KbdGroup></div></SidebarInset>
          </SidebarProvider>
          <Pagination><PaginationContent><PaginationItem><PaginationPrevious href="#" /></PaginationItem><PaginationItem><PaginationLink href="#" isActive>1</PaginationLink></PaginationItem><PaginationItem><PaginationLink href="#">2</PaginationLink></PaginationItem><PaginationItem><PaginationEllipsis /></PaginationItem><PaginationItem><PaginationNext href="#" /></PaginationItem></PaginationContent></Pagination>
          <div className="flex items-center gap-3"><Skeleton className="h-8 w-40" /><Spinner /><span className="text-sm text-muted-foreground">Saving changes</span></div>
        </section>
      </div>
      <Toaster />
    </TooltipProvider>
  )
}

export { DevUIPage }

#include <sys/mman.h>
#include <fcntl.h>
#include <errno.h>
#include "main.h"
#include "MyFrame.h"

const int ID_OPENx = 101;
const int ID_OPENy1 = 102;
const int ID_OPENy2 = 103;
const int ID_STARTDRAW = 104;
const int ID_TOGGLE_CURVE1 = 105;
const int ID_TOGGLE_CURVE2 = 106;

BEGIN_EVENT_TABLE(MyFrame, wxFrame)
    EVT_MENU(ID_OPENx, MyFrame::OnOpen)
    EVT_MENU(ID_OPENy1, MyFrame::OnOpen)
    EVT_MENU(ID_OPENy2, MyFrame::OnOpen)
    EVT_MENU(ID_STARTDRAW, MyFrame::OnStartDraw)
    EVT_MENU(ID_TOGGLE_CURVE1, MyFrame::OnToggle1)
    EVT_MENU(ID_TOGGLE_CURVE2, MyFrame::OnToggle2)
END_EVENT_TABLE()

MyFrame::MyFrame()
: wxFrame(NULL, -1, wxT("Sample"), wxDefaultPosition)
{
    m_xmap = (unsigned int*)-1;
    m_xmap = (unsigned int*)-1;
    m_cur1x = 0;
    m_cur2x = 0;
    wxMenu *menuFile = new wxMenu;

    menuFile->Append(ID_OPENx, wxT("Open&X"));
    menuFile->Append(ID_OPENy1, wxT("OpenY&1"));
    menuFile->Append(ID_OPENy2, wxT("OpenY&2"));
    menuFile->Append(ID_STARTDRAW, wxT("&Draw"));
    
    wxMenu *menuShow = new wxMenu;
    menuShow->AppendCheckItem(ID_TOGGLE_CURVE1, wxT("Curve 1"));
    menuShow->AppendCheckItem(ID_TOGGLE_CURVE2, wxT("Curve 2"));
    menuShow->Check(ID_TOGGLE_CURVE1, true);
    menuShow->Check(ID_TOGGLE_CURVE2, true);
    
    wxMenuBar *menuBar = new wxMenuBar;
    menuBar->Append(menuFile, _("&File"));
    menuBar->Append(menuShow, _("&Menu"));

    m_log = new wxTextCtrl( this, -1, wxT("Dynamic stats will appear here..."), wxPoint(0,0), wxSize(100,100), wxTE_MULTILINE );
    wxFont graphFont(16, wxFONTFAMILY_DEFAULT, wxFONTSTYLE_NORMAL, wxFONTWEIGHT_NORMAL);
    m_log->SetFont(graphFont);

    /* Will be m_plots[] */
    m_plot1 = new MyMpWindow(this, -1, wxPoint(0,0), wxSize(400,50), wxSUNKEN_BORDER);
    m_plot2 = new MyMpWindow(this, -1, wxPoint(0,0), wxSize(400,50), wxSUNKEN_BORDER);
    m_plot3 = new MyMpWindow(this, -1, wxPoint(0,0), wxSize(400,50), wxSUNKEN_BORDER);
    m_plot4 = new MyMpWindow(this, -1, wxPoint(0,0), wxSize(400,50), wxSUNKEN_BORDER);
    m_plot5 = new MyMpWindow(this, -1, wxPoint(0,0), wxSize(400,50), wxSUNKEN_BORDER);
    m_plot6 = new MyMpWindow(this, -1, wxPoint(0,0), wxSize(400,50), wxSUNKEN_BORDER);
            
    wxBoxSizer *horizontal_sizer = new wxBoxSizer( wxHORIZONTAL );
    wxBoxSizer *vertical_sizer = new wxBoxSizer(wxVERTICAL);
    vertical_sizer->Add(m_plot1, 1, wxEXPAND);
    vertical_sizer->Add(m_plot2, 1, wxEXPAND);
    vertical_sizer->Add(m_plot3, 1, wxEXPAND);
    vertical_sizer->Add(m_plot4, 1, wxEXPAND);
    vertical_sizer->Add(m_plot5, 1, wxEXPAND);
    vertical_sizer->Add(m_plot6, 1, wxEXPAND);
    horizontal_sizer->Add(vertical_sizer, 4, wxEXPAND);
    horizontal_sizer->Add(m_log, 1, wxEXPAND);

    SetAutoLayout(TRUE);
    SetSizer(horizontal_sizer);
    
    SetMenuBar( menuBar );
    CreateStatusBar();
    SetStatusText( _("Welcome to Artist") );
}

void MyFrame::updateStatusText(wxString str)
{
    SetStatusText(str);
}

void MyFrame::OnOpen(wxCommandEvent& event)
{
    int id, fd = -1;
    wxString filename;
    wxFileDialog * openFileDialog = new wxFileDialog(this);
    id = event.GetId();
    
    if (openFileDialog->ShowModal() == wxID_OK){
        filename = openFileDialog->GetPath();        
        fd = open(filename.mb_str(), O_RDONLY);
        if (fd < 0){
            wxMessageDialog *dial = new wxMessageDialog(NULL,
                    wxString::Format(_("Can't open file: %d"), errno), wxT("ERROR"), wxOK);
            dial->ShowModal();
        }
        if (id == 101){
            m_xfd = fd;
        } else if (id == 102){
            m_y1fd = fd;
        } else if (id == 103){
            m_y2fd = fd;
        }
    }
    SetStatusText(wxString::Format(_("Calling %d"), id));
}

void MyFrame::OnStartDraw(wxCommandEvent& event)
{
    /* memory mapping files */
    double max_x = 0, min_x = 0, third_x;
    if (m_xfd >= 0 && m_y1fd >= 0 && m_y2fd >= 0){
        m_xmap = (unsigned int *)mmap(NULL, 400, PROT_READ, MAP_SHARED, m_xfd, 0);
        if (m_xmap == (unsigned int*)-1){
            wxMessageDialog *dial = new wxMessageDialog
                    (NULL, wxT("Can't map x file"), wxT("ERROR"), wxOK);
            dial->ShowModal();
            return;
        }
        m_ymap = (unsigned int *)mmap(NULL, 400, PROT_READ, MAP_SHARED, m_y1fd, 0);
        if (m_ymap == (unsigned int*)-1){
            wxMessageDialog *dial = new wxMessageDialog
                    (NULL, wxT("Can't map y1 file"), wxT("ERROR"), wxOK);
            dial->ShowModal();
            munmap(m_xmap, 400);
            m_xmap = (unsigned int *)-1;
            return;
        }
        m_y1map = (unsigned int *)mmap(NULL, 400, PROT_READ, MAP_SHARED, m_y2fd, 0);
        if (m_y1map == (unsigned int*)-1){
            wxMessageDialog *dial = new wxMessageDialog
                    (NULL, wxT("Can't map y2 file"), wxT("ERROR"), wxOK);
            dial->ShowModal();
            munmap(m_ymap, 400);
            m_ymap = (unsigned int *)-1;
            munmap(m_xmap, 400);
            m_xmap = (unsigned int *)-1;
            return;
        }
        
    } else {
        wxMessageDialog *dial = new wxMessageDialog(NULL,
                wxT("files are invalid"), wxT("ERROR"), wxOK);
        dial->ShowModal();
        return;
    }
    
    /* Get the first X and last X */
    max_x = 2147483647;
    min_x = 0;

    m_plot1->SetMargins(30, 30, 50, 100);
    
    m_plot1->move_cur1(min_x);
    m_plot1->move_cur2(max_x);
    m_plot1->StartDraw(m_xmap, m_ymap, m_y1map);
    m_plot2->StartDraw(m_xmap, m_ymap, m_y1map);
    m_plot3->StartDraw(m_xmap, m_ymap, m_y1map);
    m_plot4->StartDraw(m_xmap, m_ymap, m_y1map);
    m_plot5->StartDraw(m_xmap, m_ymap, m_y1map);
    m_plot6->StartDraw(m_xmap, m_ymap, m_y1map);
}

void MyFrame::OnToggle1(wxCommandEvent& event)
{
    m_plot1->SetLayerVisible(wxT("curve 1"), event.IsChecked());
}

void MyFrame::OnToggle2(wxCommandEvent& event)
{
    m_plot1->SetLayerVisible(wxT("curve 2"), event.IsChecked());
}

MyFrame::~MyFrame()
{
    if (m_xmap != (unsigned int*)-1){
        munmap(m_xmap, 400);
    }
    if (m_ymap != (unsigned int*)-1){
        munmap(m_ymap, 400);
    }
    if (m_y1map != (unsigned int*)-1){
        munmap(m_y1map, 400);
    }
}

void MyFrame::move_cur1(double x)
{
    m_cur1x = x;
    m_plot1->move_cur1(x);
    m_plot2->move_cur1(x);
    m_plot3->move_cur1(x);
    m_plot4->move_cur1(x);
    m_plot5->move_cur1(x);
    m_plot6->move_cur1(x);
}

void MyFrame::move_cur2(double x)
{
    m_cur2x = x;
    m_plot1->move_cur2(x);
    m_plot2->move_cur2(x);
    m_plot3->move_cur2(x);
    m_plot4->move_cur2(x);
    m_plot5->move_cur2(x);
    m_plot6->move_cur2(x);
}

void MyFrame::stats()
{
    m_log->Clear();
    m_log->WriteText(wxString::Format(_("cur1 at %f\ncur2 at %f\ninterval is %f"),
            m_cur1x, m_cur2x, m_cur2x - m_cur1x));    
    m_log->Update();
}
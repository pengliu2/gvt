#include "MyMpWindow.h"
#include "main.h"
#include "MyFrame.h"


IMPLEMENT_DYNAMIC_CLASS(MyMpWindow, mpWindow)

BEGIN_EVENT_TABLE(MyMpWindow, mpWindow)
    EVT_RIGHT_DOWN(MyMpWindow::OnMouseRightDown)
    EVT_RIGHT_UP(MyMpWindow::OnMouseRightUp)
    EVT_LEFT_DOWN(MyMpWindow::OnMouseLeftDown)
    EVT_LEFT_UP(MyMpWindow::OnMouseLeftRelease)
    EVT_MOTION( MyMpWindow::OnMouseMove)
END_EVENT_TABLE()

MyMpWindow::MyMpWindow(wxWindow* parent, wxWindowID id, const wxPoint& pos, const wxSize& size, long flag)
: mpWindow(parent, id, pos, size, flag)
{
    m_cross_cursor1 = false;
    m_moving_cursor1 = false;
    m_moving_cursor2 = false;
    m_cur1_layer = new MyCursor(0, _("cur1"));
    m_cur2_layer = new MyCursor(0, _("cur2"));
    wxPen greenpen(*wxGREEN, 1, wxSOLID);
    m_cur1_layer->SetPen(greenpen);
    m_cur2_layer->SetPen(greenpen);
    AddLayer(m_cur1_layer);
    AddLayer(m_cur2_layer);
    /*
    m_cur1 = new MyCursor(m_cur1, wxT("cursor 1"));
    wxPen greenpen(*wxGREEN, 1, wxSOLID);
    m_plot->cur1_layer->SetPen(greenpen);
    m_plot->AddLayer(m_plot->cur1_layer);
    
    m_plot->cur2_layer = new MyCursor(m_cur2, wxT("cursor 2"));
    m_plot->cur2_layer->SetPen(greenpen);
    m_plot->AddLayer(m_plot->cur2_layer);
    */
}

void MyMpWindow::OnMouseRightDown(wxMouseEvent & event)
{
    return;
}

void MyMpWindow::OnMouseRightUp(wxMouseEvent& event)
{
    return;
}

void MyMpWindow::OnMouseLeftDown(wxMouseEvent& event)
{
    if (m_cross_cursor1){
        SetCursor(wxCURSOR_HAND);
        m_moving_cursor1 = true;
    } else if (m_cross_cursor2){
        SetCursor(wxCURSOR_HAND);
        m_moving_cursor2 = true;
    }
    return;
}

void MyMpWindow::OnMouseLeftRelease(wxMouseEvent& event)
{
    if (m_moving_cursor1){
        ((MyFrame *)m_parent)->stats();
    } else if (m_moving_cursor2){
        ((MyFrame *)m_parent)->stats();
    }
    m_moving_cursor1 = false;
    m_moving_cursor2 = false;
    SetCursor(*wxSTANDARD_CURSOR);
    return;
}

void MyMpWindow::OnMouseMove(wxMouseEvent& event)
{
    wxCoord p = event.GetX();
    double x = p2x(p);

    if (event.LeftIsDown()){
        if (m_moving_cursor1){
            ((MyFrame *)m_parent)->move_cur1(x);
        } else if (m_moving_cursor2){
            ((MyFrame *)m_parent)->move_cur2(x);
        }
    } else if (m_cur1_layer != NULL && m_cur2_layer != NULL){
        int x1 = abs(p - x2p(m_cur1_layer->getP()));
        int x2 = abs(p - x2p(m_cur2_layer->getP()));
        if (!m_cross_cursor1 && !m_cross_cursor2){
            if (x1 <= 1){
                SetCursor(*wxCROSS_CURSOR);
                m_cross_cursor1 = true;
            } else if  (x2 <= 1){
                SetCursor(*wxCROSS_CURSOR);
                m_cross_cursor2 = true;
            }
        } else if (x1 > 1 and x2 > 1){
            SetCursor(*wxSTANDARD_CURSOR);
            m_cross_cursor1 = false;
            m_cross_cursor2 = false;
        }
        ((MyFrame *)m_parent)->updateStatusText(wxString::Format(_("mouse to %f,%d, (%f,%f)"), x, p, m_cur1_layer->getP(), m_cur2_layer->getP()));
    }
    return;
}

void MyMpWindow::move_cur1(double x)
{
    m_cur1_layer->move(x);
    UpdateAll();
}

void MyMpWindow::move_cur2(double x)
{
    m_cur2_layer->move(x);
    UpdateAll();
}

void MyMpWindow::StartDraw(unsigned int *x, unsigned int *y, unsigned int *y1)
{
    mpScaleX* xaxis = new mpScaleX(wxT("X"), mpALIGN_BOTTOM, true, mpX_NORMAL);
    mpScaleY* yaxis = new mpScaleY(wxT("Y"), mpALIGN_LEFT, true);
    wxFont graphFont(11, wxFONTFAMILY_DEFAULT, wxFONTSTYLE_NORMAL, wxFONTWEIGHT_NORMAL);
    xaxis->SetFont(graphFont);
    yaxis->SetFont(graphFont);
    xaxis->SetDrawOutsideMargins(false);
    yaxis->SetDrawOutsideMargins(false);
    AddLayer(     xaxis );
    AddLayer(     yaxis );
    MyCurve *l1 = new MyCurve(x, y, 100, wxT("curve 1"));
    l1->SetContinuity(TRUE);
    wxPen bluepen(*wxBLUE, 1, wxSOLID);
    l1->SetPen(bluepen);
    AddLayer(l1);
    MyEvent *l2 = new MyEvent(x, y1, 100, wxT("event 1"), 1024);
    l2->SetContinuity(TRUE);
    wxPen redpen(*wxRED, 1, wxSOLID);
    l2->SetPen(redpen);
    AddLayer(l2);
    Fit();

}

/*
void MyMpWindow::StartDraw(MyFrame::Curve *curves, int count)
{
    
}
 */

